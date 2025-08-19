#!/usr/bin/env python3
"""
CyRIS 现代化部署脚本
分步骤执行系统部署和验证
"""
import sys
import subprocess
import argparse
import logging
from pathlib import Path
from typing import List, Dict, Any
import json
import time

# 设置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)


class DeploymentError(Exception):
    """部署错误"""
    pass


class DeploymentStep:
    """部署步骤基类"""
    
    def __init__(self, name: str, description: str):
        self.name = name
        self.description = description
        self.start_time = None
        self.end_time = None
        self.status = "pending"  # pending, running, success, failed
        self.error_message = None
    
    def execute(self) -> bool:
        """执行步骤"""
        raise NotImplementedError
    
    def validate(self) -> bool:
        """验证步骤结果"""
        return True
    
    def rollback(self) -> bool:
        """回滚步骤"""
        return True
    
    def get_duration(self) -> float:
        """获取执行时间"""
        if self.start_time and self.end_time:
            return self.end_time - self.start_time
        return 0


class HostPreparationStep(DeploymentStep):
    """主机准备步骤"""
    
    def __init__(self):
        super().__init__(
            "host_preparation", 
            "准备主机环境，安装必要的系统包"
        )
    
    def execute(self) -> bool:
        """执行主机准备"""
        try:
            logger.info("开始主机准备...")
            
            # 检查是否为Ubuntu
            result = subprocess.run(
                ['lsb_release', '-i'], 
                capture_output=True, 
                text=True,
                check=True
            )
            
            if 'Ubuntu' not in result.stdout:
                logger.warning("当前系统不是Ubuntu，可能需要调整安装命令")
            
            # 更新包列表
            logger.info("更新包列表...")
            subprocess.run(['apt', 'update'], check=True)
            
            # 安装基础包
            packages = [
                'python3-full',
                'python3-pip',
                'python3-venv',
                'qemu-kvm',
                'libvirt-daemon-system',
                'libvirt-clients',
                'bridge-utils',
                'virt-manager',
                'python3-paramiko',
                'tcpreplay',
                'wireshark-common',
                'sshpass',
                'pssh',
                'sendemail'
            ]
            
            logger.info(f"安装必需包: {', '.join(packages)}")
            subprocess.run(['apt', 'install', '-y'] + packages, check=True)
            
            return True
            
        except subprocess.CalledProcessError as e:
            self.error_message = f"Host preparation failed: {e}"
            logger.error(self.error_message)
            return False
        except Exception as e:
            self.error_message = f"Unexpected error in host preparation: {e}"
            logger.error(self.error_message)
            return False
    
    def validate(self) -> bool:
        """验证主机准备结果"""
        try:
            # 检查Python虚拟环境支持
            subprocess.run(['python3', '-m', 'venv', '--help'], 
                          capture_output=True, check=True)
            
            # 检查KVM支持
            subprocess.run(['kvm-ok'], capture_output=True)
            
            # 检查libvirt服务
            result = subprocess.run(
                ['systemctl', 'is-active', 'libvirtd'], 
                capture_output=True, text=True
            )
            
            if result.returncode != 0:
                logger.warning("libvirtd service is not active")
            
            return True
            
        except subprocess.CalledProcessError:
            return False


class PythonEnvironmentStep(DeploymentStep):
    """Python环境设置步骤"""
    
    def __init__(self, project_root: Path):
        super().__init__(
            "python_environment",
            "创建Python虚拟环境并安装依赖"
        )
        self.project_root = project_root
        self.venv_path = project_root / '.venv'
    
    def execute(self) -> bool:
        """执行Python环境设置"""
        try:
            logger.info("设置Python虚拟环境...")
            
            # 创建虚拟环境
            if not self.venv_path.exists():
                subprocess.run([
                    'python3', '-m', 'venv', str(self.venv_path)
                ], check=True)
                logger.info(f"虚拟环境已创建: {self.venv_path}")
            else:
                logger.info("虚拟环境已存在")
            
            # 激活虚拟环境并安装依赖
            pip_path = self.venv_path / 'bin' / 'pip'
            
            # 更新pip
            subprocess.run([str(pip_path), 'install', '--upgrade', 'pip'], 
                          check=True)
            
            # 安装基础依赖
            base_packages = [
                'pytest>=7.0.0',
                'pytest-cov>=4.0.0',
                'pytest-mock>=3.10.0',
                'pydantic>=2.0.0',
                'pydantic-settings>=2.0.0',
                'pyyaml>=6.0.0',
                'boto3>=1.34.0',
                'paramiko>=3.0.0',
                'psutil>=5.9.0',
                'structlog>=23.0.0',
                'click>=8.0.0'
            ]
            
            logger.info("安装Python依赖包...")
            subprocess.run([str(pip_path), 'install'] + base_packages, 
                          check=True)
            
            return True
            
        except subprocess.CalledProcessError as e:
            self.error_message = f"Python environment setup failed: {e}"
            logger.error(self.error_message)
            return False
    
    def validate(self) -> bool:
        """验证Python环境"""
        try:
            python_path = self.venv_path / 'bin' / 'python'
            
            # 检查Python版本
            result = subprocess.run([
                str(python_path), '--version'
            ], capture_output=True, text=True, check=True)
            
            logger.info(f"Python version: {result.stdout.strip()}")
            
            # 检查关键包
            subprocess.run([
                str(python_path), '-c', 
                'import pytest, pydantic, yaml, boto3, paramiko'
            ], check=True)
            
            return True
            
        except subprocess.CalledProcessError:
            return False


class NetworkConfigurationStep(DeploymentStep):
    """网络配置步骤"""
    
    def __init__(self):
        super().__init__(
            "network_configuration",
            "配置网络桥接和防火墙规则"
        )
    
    def execute(self) -> bool:
        """执行网络配置"""
        try:
            logger.info("配置网络环境...")
            
            # 检查网络桥接支持
            result = subprocess.run(
                ['brctl', 'show'], 
                capture_output=True, 
                text=True,
                check=True
            )
            
            logger.info("网络桥接支持已确认")
            
            # 确保用户在libvirt组中
            import os
            username = os.getenv('USER', 'ubuntu')
            
            try:
                subprocess.run([
                    'usermod', '-a', '-G', 'libvirt', username
                ], check=True)
                logger.info(f"用户 {username} 已添加到 libvirt 组")
            except subprocess.CalledProcessError:
                logger.warning("无法添加用户到libvirt组，可能需要手动操作")
            
            return True
            
        except subprocess.CalledProcessError as e:
            self.error_message = f"Network configuration failed: {e}"
            logger.error(self.error_message)
            return False
    
    def validate(self) -> bool:
        """验证网络配置"""
        try:
            # 检查libvirt网络
            result = subprocess.run([
                'virsh', 'net-list', '--all'
            ], capture_output=True, text=True)
            
            if result.returncode == 0:
                logger.info("libvirt网络配置正常")
                return True
            else:
                logger.warning("libvirt网络配置可能有问题")
                return False
                
        except subprocess.CalledProcessError:
            return False


class TestExecutionStep(DeploymentStep):
    """测试执行步骤"""
    
    def __init__(self, project_root: Path):
        super().__init__(
            "test_execution",
            "运行单元测试验证系统功能"
        )
        self.project_root = project_root
    
    def execute(self) -> bool:
        """执行测试"""
        try:
            logger.info("运行单元测试...")
            
            venv_python = self.project_root / '.venv' / 'bin' / 'python'
            
            # 运行测试
            result = subprocess.run([
                str(venv_python), '-m', 'pytest',
                'tests/unit/',
                '-v',
                '--tb=short'
            ], 
            cwd=self.project_root,
            capture_output=True,
            text=True
            )
            
            if result.returncode == 0:
                logger.info("所有单元测试通过")
                return True
            else:
                self.error_message = f"Tests failed:\n{result.stdout}\n{result.stderr}"
                logger.error("单元测试失败")
                logger.error(result.stdout)
                logger.error(result.stderr)
                return False
                
        except subprocess.CalledProcessError as e:
            self.error_message = f"Test execution failed: {e}"
            logger.error(self.error_message)
            return False


class CyRISDeployer:
    """CyRIS部署器"""
    
    def __init__(self, project_root: Path, config_file: Path = None):
        self.project_root = project_root
        self.config_file = config_file
        self.steps: List[DeploymentStep] = []
        self.deployment_log = []
        
        # 初始化部署步骤
        self._initialize_steps()
    
    def _initialize_steps(self):
        """初始化部署步骤"""
        self.steps = [
            HostPreparationStep(),
            PythonEnvironmentStep(self.project_root),
            NetworkConfigurationStep(),
            TestExecutionStep(self.project_root)
        ]
    
    def run_deployment(self, skip_steps: List[str] = None) -> bool:
        """运行部署"""
        skip_steps = skip_steps or []
        success = True
        
        logger.info("开始CyRIS现代化部署...")
        logger.info(f"项目根目录: {self.project_root}")
        
        for step in self.steps:
            if step.name in skip_steps:
                logger.info(f"跳过步骤: {step.name}")
                continue
            
            logger.info(f"执行步骤: {step.name} - {step.description}")
            
            step.status = "running"
            step.start_time = time.time()
            
            try:
                if step.execute():
                    if step.validate():
                        step.status = "success"
                        logger.info(f"✓ 步骤 {step.name} 执行成功")
                    else:
                        step.status = "failed"
                        step.error_message = "Validation failed"
                        logger.error(f"✗ 步骤 {step.name} 验证失败")
                        success = False
                else:
                    step.status = "failed"
                    logger.error(f"✗ 步骤 {step.name} 执行失败: {step.error_message}")
                    success = False
            
            except Exception as e:
                step.status = "failed"
                step.error_message = str(e)
                logger.error(f"✗ 步骤 {step.name} 发生异常: {e}")
                success = False
            
            finally:
                step.end_time = time.time()
            
            self.deployment_log.append({
                'step': step.name,
                'status': step.status,
                'duration': step.get_duration(),
                'error': step.error_message
            })
        
        self._print_summary()
        return success
    
    def _print_summary(self):
        """打印部署摘要"""
        logger.info("\n" + "="*60)
        logger.info("部署摘要")
        logger.info("="*60)
        
        total_time = 0
        success_count = 0
        
        for log_entry in self.deployment_log:
            status_symbol = "✓" if log_entry['status'] == 'success' else "✗"
            duration = log_entry['duration']
            total_time += duration
            
            if log_entry['status'] == 'success':
                success_count += 1
            
            logger.info(f"{status_symbol} {log_entry['step']}: {duration:.2f}s")
            
            if log_entry['error']:
                logger.info(f"  错误: {log_entry['error']}")
        
        logger.info("-"*60)
        logger.info(f"总耗时: {total_time:.2f}s")
        logger.info(f"成功步骤: {success_count}/{len(self.deployment_log)}")
        
        if success_count == len(self.deployment_log):
            logger.info("🎉 部署完成！CyRIS现代化部署成功")
        else:
            logger.error("❌ 部署失败，请检查错误信息")


def main():
    """主函数"""
    parser = argparse.ArgumentParser(description='CyRIS现代化部署脚本')
    parser.add_argument('--project-root', type=Path, default=Path.cwd(),
                       help='项目根目录路径')
    parser.add_argument('--config', type=Path,
                       help='配置文件路径')
    parser.add_argument('--skip-steps', nargs='+', 
                       help='要跳过的步骤名称列表')
    parser.add_argument('--dry-run', action='store_true',
                       help='干运行模式，只显示将要执行的步骤')
    
    args = parser.parse_args()
    
    if args.dry_run:
        deployer = CyRISDeployer(args.project_root, args.config)
        logger.info("干运行模式 - 将执行以下步骤:")
        for step in deployer.steps:
            if not args.skip_steps or step.name not in args.skip_steps:
                logger.info(f"  - {step.name}: {step.description}")
        return 0
    
    try:
        deployer = CyRISDeployer(args.project_root, args.config)
        success = deployer.run_deployment(args.skip_steps)
        return 0 if success else 1
        
    except KeyboardInterrupt:
        logger.info("部署被用户中断")
        return 1
    except Exception as e:
        logger.error(f"部署过程中发生未预期的错误: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())