"""
Cyber Range Discovery Service
Discover and synchronize unmanaged cyber range resources
"""
import logging
import re
import json
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Set, Tuple, Optional, Any
from dataclasses import dataclass

from cyris.config.settings import CyRISSettings
from cyris.services.orchestrator import RangeOrchestrator, RangeStatus, RangeMetadata
from cyris.infrastructure.providers.virsh_client import VirshLibvirt
from cyris.core.exceptions import CyRISException


logger = logging.getLogger(__name__)


@dataclass
class OrphanedResource:
    """Orphaned resource information"""
    resource_type: str  # 'vm', 'disk', 'directory'
    name: str
    path: Optional[str] = None
    state: Optional[str] = None
    created_time: Optional[datetime] = None
    size: Optional[int] = None  # for disk files
    range_id: Optional[str] = None  # inferred range ID


class RangeDiscoveryService:
    """Cyber range discovery service"""
    
    def __init__(self, settings: CyRISSettings, orchestrator: RangeOrchestrator):
        """
        Initialize discovery service
        
        Args:
            settings: CyRIS configuration
            orchestrator: Orchestrator service instance
        """
        self.settings = settings
        self.orchestrator = orchestrator
        self.virsh_client = VirshLibvirt()
        
        # VM naming patterns
        self.vm_patterns = {
            # New format: cyris-<type>-<shortid>
            'new_format': re.compile(r'^cyris-([a-z]+)-([a-f0-9]{8})$'),
            # Old format: cyris-<uuid>-<suffix> 
            'old_format': re.compile(r'^cyris-([a-f0-9-]{36})-([a-f0-9]{8})$'),
        }
        
        # Disk file naming patterns
        self.disk_patterns = {
            'new_format': re.compile(r'^cyris-([a-z]+)-([a-f0-9]{8})\.qcow2$'),
            'old_format': re.compile(r'^cyris-([a-f0-9-]{36})-([a-f0-9]{8})\.qcow2$'),
        }
        
        logger.info("RangeDiscoveryService initialized")
    
    def discover_all_ranges(self) -> Dict[str, Any]:
        """
        发现所有靶场资源
        
        Returns:
            Dict: 发现结果统计
        """
        logger.info("Starting comprehensive range discovery...")
        
        # 获取当前管理的靶场
        managed_ranges = set(self.orchestrator._ranges.keys())
        logger.info(f"Currently managed ranges: {managed_ranges}")
        
        # 发现各种资源
        vms = self._discover_virtual_machines()
        disks = self._discover_disk_files()
        directories = self._discover_range_directories()
        
        # 分析孤立资源
        orphaned_vms = self._identify_orphaned_vms(vms, managed_ranges)
        orphaned_disks = self._identify_orphaned_disks(disks, managed_ranges)
        orphaned_dirs = self._identify_orphaned_directories(directories, managed_ranges)
        
        # 推断可能的靶场
        inferred_ranges = self._infer_missing_ranges(orphaned_vms, orphaned_disks, orphaned_dirs)
        
        discovery_result = {
            'timestamp': datetime.now().isoformat(),
            'managed_ranges': list(managed_ranges),
            'discovered_vms': len(vms),
            'discovered_disks': len(disks),
            'discovered_directories': len(directories),
            'orphaned_vms': len(orphaned_vms),
            'orphaned_disks': len(orphaned_disks),
            'orphaned_directories': len(orphaned_dirs),
            'inferred_ranges': list(inferred_ranges.keys()),
            'total_orphaned_resources': len(orphaned_vms) + len(orphaned_disks) + len(orphaned_dirs)
        }
        
        logger.info(f"Discovery completed: {discovery_result}")
        return discovery_result
    
    def _discover_virtual_machines(self) -> List[OrphanedResource]:
        """Discover virtual machines"""
        vms = []
        
        try:
            # 获取所有虚拟机
            all_vms = self.virsh_client.list_all_domains()
            
            for vm in all_vms:
                if vm['name'].startswith('cyris-'):
                    # 提取可能的range_id
                    range_id = self._extract_range_id_from_vm(vm['name'])
                    
                    resource = OrphanedResource(
                        resource_type='vm',
                        name=vm['name'],
                        state=vm['state'],
                        range_id=range_id
                    )
                    vms.append(resource)
            
            logger.info(f"Discovered {len(vms)} CyRIS virtual machines")
            
        except Exception as e:
            logger.error(f"Failed to discover virtual machines: {e}")
        
        return vms
    
    def _discover_disk_files(self) -> List[OrphanedResource]:
        """Discover disk files"""
        disks = []
        
        try:
            cyber_range_dir = Path(self.settings.cyber_range_dir)
            
            # 查找所有.qcow2文件
            for disk_file in cyber_range_dir.glob("*.qcow2"):
                if disk_file.name.startswith('cyris-'):
                    # 提取可能的range_id
                    range_id = self._extract_range_id_from_disk(disk_file.name)
                    
                    resource = OrphanedResource(
                        resource_type='disk',
                        name=disk_file.name,
                        path=str(disk_file),
                        size=disk_file.stat().st_size,
                        created_time=datetime.fromtimestamp(disk_file.stat().st_ctime),
                        range_id=range_id
                    )
                    disks.append(resource)
            
            logger.info(f"Discovered {len(disks)} disk files")
            
        except Exception as e:
            logger.error(f"Failed to discover disk files: {e}")
        
        return disks
    
    def _discover_range_directories(self) -> List[OrphanedResource]:
        """发现靶场目录"""
        directories = []
        
        try:
            cyber_range_dir = Path(self.settings.cyber_range_dir)
            
            # 查找数字命名的目录（Range ID）
            for item in cyber_range_dir.iterdir():
                if item.is_dir() and item.name.isdigit():
                    resource = OrphanedResource(
                        resource_type='directory',
                        name=item.name,
                        path=str(item),
                        created_time=datetime.fromtimestamp(item.stat().st_ctime),
                        range_id=item.name
                    )
                    directories.append(resource)
            
            logger.info(f"Discovered {len(directories)} range directories")
            
        except Exception as e:
            logger.error(f"Failed to discover range directories: {e}")
        
        return directories
    
    def _extract_range_id_from_vm(self, vm_name: str) -> Optional[str]:
        """从虚拟机名称提取range_id"""
        # 简化的推断逻辑 - 实际实现可能需要更复杂的分析
        # 目前无法从UUID格式的名称直接推断range_id
        return None
    
    def _extract_range_id_from_disk(self, disk_name: str) -> Optional[str]:
        """从磁盘文件名提取range_id"""
        # 简化的推断逻辑
        return None
    
    def _identify_orphaned_vms(
        self, 
        vms: List[OrphanedResource], 
        managed_ranges: Set[str]
    ) -> List[OrphanedResource]:
        """识别孤立的虚拟机"""
        orphaned = []
        
        for vm in vms:
            # 检查VM是否属于已管理的靶场
            vm_managed = False
            
            # 检查是否在已管理靶场的资源列表中
            for range_id in managed_ranges:
                range_resources = self.orchestrator._range_resources.get(range_id, {})
                vms_in_range = range_resources.get('vms', [])
                if vm.name in vms_in_range:
                    vm_managed = True
                    break
            
            if not vm_managed:
                orphaned.append(vm)
        
        return orphaned
    
    def _identify_orphaned_disks(
        self,
        disks: List[OrphanedResource],
        managed_ranges: Set[str]
    ) -> List[OrphanedResource]:
        """识别孤立的磁盘文件"""
        orphaned = []
        
        for disk in disks:
            # 检查磁盘是否属于已管理的靶场
            disk_managed = False
            
            for range_id in managed_ranges:
                range_resources = self.orchestrator._range_resources.get(range_id, {})
                disks_in_range = range_resources.get('disks', [])
                if disk.name in disks_in_range:
                    disk_managed = True
                    break
            
            if not disk_managed:
                orphaned.append(disk)
        
        return orphaned
    
    def _identify_orphaned_directories(
        self,
        directories: List[OrphanedResource], 
        managed_ranges: Set[str]
    ) -> List[OrphanedResource]:
        """识别孤立的靶场目录"""
        orphaned = []
        
        for directory in directories:
            if directory.name not in managed_ranges:
                orphaned.append(directory)
        
        return orphaned
    
    def _infer_missing_ranges(
        self,
        orphaned_vms: List[OrphanedResource],
        orphaned_disks: List[OrphanedResource], 
        orphaned_dirs: List[OrphanedResource]
    ) -> Dict[str, Dict[str, List[str]]]:
        """推断缺失的靶场"""
        inferred_ranges = {}
        
        # 从孤立目录推断靶场
        for directory in orphaned_dirs:
            range_id = directory.name
            if range_id not in inferred_ranges:
                inferred_ranges[range_id] = {
                    'directories': [],
                    'vms': [],
                    'disks': []
                }
            inferred_ranges[range_id]['directories'].append(directory.name)
        
        # 尝试将孤立的VM和磁盘关联到推断的靶场
        # 这里使用简化的逻辑，实际可能需要更复杂的匹配算法
        
        return inferred_ranges
    
    def recover_missing_ranges(
        self, 
        range_ids: List[str] = None,
        dry_run: bool = True
    ) -> Dict[str, Any]:
        """
        恢复缺失的靶场到管理系统
        
        Args:
            range_ids: 要恢复的Range ID列表，None表示恢复所有发现的
            dry_run: 是否只是模拟运行
            
        Returns:
            Dict: 恢复结果
        """
        logger.info(f"Starting range recovery (dry_run={dry_run})...")
        
        # 先发现所有资源
        discovery_result = self.discover_all_ranges()
        
        # 获取孤立目录作为需要恢复的靶场
        directories = self._discover_range_directories()
        managed_ranges = set(self.orchestrator._ranges.keys())
        orphaned_dirs = self._identify_orphaned_directories(directories, managed_ranges)
        
        if range_ids:
            # 只恢复指定的靶场
            orphaned_dirs = [d for d in orphaned_dirs if d.name in range_ids]
        
        recovery_result = {
            'timestamp': datetime.now().isoformat(),
            'dry_run': dry_run,
            'ranges_to_recover': [d.name for d in orphaned_dirs],
            'recovered_ranges': [],
            'failed_ranges': []
        }
        
        for directory in orphaned_dirs:
            range_id = directory.name
            
            try:
                if not dry_run:
                    # Create range metadata
                    metadata = RangeMetadata(
                        range_id=range_id,
                        name=f"Range {range_id}",
                        description=f"Recovered range {range_id}",
                        status=RangeStatus.ACTIVE,  # 假设是活跃的，可以后续验证
                        created_at=directory.created_time or datetime.now()
                    )
                    
                    # 添加到编排器
                    self.orchestrator._ranges[range_id] = metadata
                    
                    # 尝试发现这个靶场的资源
                    range_resources = self._discover_range_resources(range_id)
                    self.orchestrator._range_resources[range_id] = range_resources
                    
                    # 保存更新
                    self.orchestrator._save_persistent_data()
                    
                    logger.info(f"Recovered range {range_id}")
                
                recovery_result['recovered_ranges'].append(range_id)
                
            except Exception as e:
                logger.error(f"Failed to recover range {range_id}: {e}")
                recovery_result['failed_ranges'].append({
                    'range_id': range_id,
                    'error': str(e)
                })
        
        logger.info(f"Recovery completed: {recovery_result}")
        return recovery_result
    
    def _discover_range_resources(self, range_id: str) -> Dict[str, List[str]]:
        """发现指定靶场的资源"""
        resources = {
            'vms': [],
            'disks': [],
            'networks': []
        }
        
        try:
            # 查找与此靶场相关的虚拟机
            all_vms = self.virsh_client.list_all_domains()
            for vm in all_vms:
                # 使用启发式方法匹配VM到靶场
                # 这里需要更复杂的逻辑来正确匹配
                if self._vm_belongs_to_range(vm['name'], range_id):
                    resources['vms'].append(vm['name'])
            
            # 查找与此靶场相关的磁盘文件
            cyber_range_dir = Path(self.settings.cyber_range_dir)
            for disk_file in cyber_range_dir.glob("*.qcow2"):
                if self._disk_belongs_to_range(disk_file.name, range_id):
                    resources['disks'].append(disk_file.name)
            
        except Exception as e:
            logger.error(f"Failed to discover resources for range {range_id}: {e}")
        
        return resources
    
    def _vm_belongs_to_range(self, vm_name: str, range_id: str) -> bool:
        """判断虚拟机是否属于指定靶场"""
        # 简化的匹配逻辑
        # 实际实现需要更复杂的分析，可能需要检查VM配置或其他元数据
        return False
    
    def _disk_belongs_to_range(self, disk_name: str, range_id: str) -> bool:
        """判断磁盘文件是否属于指定靶场"""
        # 简化的匹配逻辑
        return False
    
    def cleanup_orphaned_resources(
        self, 
        resource_types: List[str] = None,
        dry_run: bool = True
    ) -> Dict[str, Any]:
        """
        清理孤立资源
        
        Args:
            resource_types: Resources to clean up类型 ['vms', 'disks', 'directories']
            dry_run: 是否只是模拟运行
            
        Returns:
            Dict: 清理结果
        """
        if resource_types is None:
            resource_types = ['vms', 'disks', 'directories']
        
        logger.info(f"Starting orphaned resource cleanup (dry_run={dry_run})...")
        
        # 发现孤立资源
        vms = self._discover_virtual_machines()
        disks = self._discover_disk_files()
        directories = self._discover_range_directories()
        
        managed_ranges = set(self.orchestrator._ranges.keys())
        
        orphaned_vms = self._identify_orphaned_vms(vms, managed_ranges) if 'vms' in resource_types else []
        orphaned_disks = self._identify_orphaned_disks(disks, managed_ranges) if 'disks' in resource_types else []
        orphaned_dirs = self._identify_orphaned_directories(directories, managed_ranges) if 'directories' in resource_types else []
        
        cleanup_result = {
            'timestamp': datetime.now().isoformat(),
            'dry_run': dry_run,
            'resource_types': resource_types,
            'orphaned_vms_found': len(orphaned_vms),
            'orphaned_disks_found': len(orphaned_disks), 
            'orphaned_directories_found': len(orphaned_dirs),
            'cleaned_vms': [],
            'cleaned_disks': [],
            'cleaned_directories': [],
            'failed_cleanups': []
        }
        
        # 清理孤立虚拟机
        for vm in orphaned_vms:
            try:
                if not dry_run:
                    self.virsh_client.destroy_domain(vm.name)
                    self.virsh_client.undefine_domain(vm.name)
                cleanup_result['cleaned_vms'].append(vm.name)
                logger.info(f"Cleaned orphaned VM: {vm.name}")
            except Exception as e:
                logger.error(f"Failed to clean VM {vm.name}: {e}")
                cleanup_result['failed_cleanups'].append({
                    'resource': vm.name,
                    'type': 'vm',
                    'error': str(e)
                })
        
        # 清理孤立磁盘文件
        for disk in orphaned_disks:
            try:
                if not dry_run:
                    Path(disk.path).unlink()
                cleanup_result['cleaned_disks'].append(disk.name)
                logger.info(f"Cleaned orphaned disk: {disk.name}")
            except Exception as e:
                logger.error(f"Failed to clean disk {disk.name}: {e}")
                cleanup_result['failed_cleanups'].append({
                    'resource': disk.name,
                    'type': 'disk', 
                    'error': str(e)
                })
        
        # 清理孤立目录
        for directory in orphaned_dirs:
            try:
                if not dry_run:
                    import shutil
                    shutil.rmtree(directory.path)
                cleanup_result['cleaned_directories'].append(directory.name)
                logger.info(f"Cleaned orphaned directory: {directory.name}")
            except Exception as e:
                logger.error(f"Failed to clean directory {directory.name}: {e}")
                cleanup_result['failed_cleanups'].append({
                    'resource': directory.name,
                    'type': 'directory',
                    'error': str(e)
                })
        
        logger.info(f"Cleanup completed: {cleanup_result}")
        return cleanup_result