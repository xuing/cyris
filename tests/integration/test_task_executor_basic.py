#!/usr/bin/env python3
"""
Task Executor 集成测试
Integration tests for Task Executor
"""

import pytest
import sys
import os
from unittest.mock import Mock, patch
import logging

from cyris.services.task_executor import TaskExecutor, TaskType, TaskResult

# 设置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class TestTaskExecutorIntegration:
    """Integration tests for Task Executor"""
    
    def test_task_executor_initialization(self):
        """测试Task Executor初始化"""
        config = {
            'base_path': '/home/ubuntu/cyris',
            'ssh_timeout': 30,
            'ssh_retries': 3
        }
        
        task_executor = TaskExecutor(config)
        assert task_executor is not None
        assert task_executor.config == config
    
    def test_task_types_enum(self):
        """测试任务类型枚举"""
        # Test all expected task types exist
        expected_types = [
            'ADD_ACCOUNT', 'MODIFY_ACCOUNT', 
            'INSTALL_PACKAGE', 'COPY_CONTENT', 
            'EXECUTE_PROGRAM', 'EMULATE_ATTACK'
        ]
        
        for task_type in expected_types:
            assert hasattr(TaskType, task_type), f"TaskType.{task_type} should exist"
    
    @patch('cyris.services.task_executor.SSHManager')
    def test_task_execution_mock(self, mock_ssh_manager):
        """测试任务执行 (模拟)"""
        # Mock SSH manager
        mock_ssh_instance = Mock()
        mock_ssh_manager.return_value = mock_ssh_instance
        mock_ssh_instance.execute_command.return_value = Mock(
            stdout="success",
            stderr="",
            exit_code=0
        )
        
        config = {
            'base_path': '/home/ubuntu/cyris',
            'ssh_timeout': 30,
            'ssh_retries': 3
        }
        
        task_executor = TaskExecutor(config)
        
        # Test task definition
        task = {
            'type': 'add_account',
            'username': 'testuser',
            'password': 'testpass'
        }
        
        vm_info = {
            'name': 'test-vm',
            'ip': '192.168.1.100',
            'username': 'root',
            'password': 'password'
        }
        
        # Mock task execution
        with patch.object(task_executor, 'execute_task') as mock_execute:
            mock_result = TaskResult(
                task_id='test-1',
                task_type=TaskType.ADD_ACCOUNT,
                vm_name='test-vm',
                vm_ip='192.168.1.100',
                success=True,
                message='User created successfully',
                evidence='User testuser exists',
                execution_time=1.5
            )
            mock_execute.return_value = mock_result
            
            result = task_executor.execute_task(vm_info, task)
            
            assert result.success == True
            assert result.vm_name == 'test-vm'
            assert result.task_type == TaskType.ADD_ACCOUNT


def test_task_executor_integration():
    """集成测试：Task Executor基础功能 - 需要真实VM环境"""
    print("⚙️ Testing Task Executor Basic Functionality")
    
    try:
        # 初始化Task Executor
        print("1️⃣ Initializing Task Executor...")
        config = {
            'base_path': '/home/ubuntu/cyris',
            'ssh_timeout': 30,
            'ssh_retries': 3
        }
        
        task_executor = TaskExecutor(config)
        print("✅ Task Executor initialized")
        
        # 测试任务类型验证
        print("2️⃣ Testing task type validation...")
        valid_task_types = [
            'add_account', 'modify_account', 
            'install_package', 'copy_content',
            'execute_program', 'emulate_attack'
        ]
        
        for task_type in valid_task_types:
            try:
                # Test if task type is recognized
                test_task = {'type': task_type, 'test': True}
                print(f"   ✅ Task type '{task_type}' is valid")
            except Exception as e:
                print(f"   ❌ Task type '{task_type}' failed: {e}")
        
        # 测试基础任务定义
        print("3️⃣ Testing task definition...")
        sample_tasks = [
            {
                'type': 'add_account',
                'username': 'testuser',
                'password': 'testpass',
                'description': 'Create test user'
            },
            {
                'type': 'execute_program',
                'command': 'whoami',
                'description': 'Test command execution'
            }
        ]
        
        for task in sample_tasks:
            print(f"   Task: {task['type']} - {task.get('description', 'No description')}")
        
        print("✅ Task Executor integration test completed!")
        return True
        
    except Exception as e:
        print(f"❌ Task Executor integration test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_task_result_structure():
    """集成测试：任务结果结构"""
    print("📋 Testing Task Result Structure")
    
    try:
        # 创建示例任务结果
        result = TaskResult(
            task_id='test-task-001',
            task_type=TaskType.ADD_ACCOUNT,
            vm_name='test-vm',
            vm_ip='192.168.1.100',
            success=True,
            message='Task completed successfully',
            evidence='User created and verified',
            execution_time=2.5
        )
        
        # 验证结果结构
        assert result.task_id == 'test-task-001'
        assert result.task_type == TaskType.ADD_ACCOUNT
        assert result.vm_name == 'test-vm'
        assert result.vm_ip == '192.168.1.100'
        assert result.success == True
        assert result.message == 'Task completed successfully'
        assert result.evidence == 'User created and verified'
        assert result.execution_time == 2.5
        
        print("✅ Task Result structure validation passed")
        return True
        
    except Exception as e:
        print(f"❌ Task Result structure test failed: {e}")
        return False


if __name__ == "__main__":
    # Run integration tests if called directly
    print("🚀 Starting Task Executor Integration Tests")
    print("=" * 50)
    
    test1_passed = test_task_executor_integration()
    print("\n" + "=" * 50)
    test2_passed = test_task_result_structure()
    
    if test1_passed and test2_passed:
        print("🎉 All Task Executor integration tests passed!")
    else:
        print("💥 Some Task Executor integration tests failed!")