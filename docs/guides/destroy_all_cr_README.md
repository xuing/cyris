# destroy_all_cr.sh v2.0.0 - 现代化批量清理脚本

## 概述

这是 CyRIS 系统全新的批量靶场清理脚本，基于我们刚实现的 Docker-style 生命周期管理系统重构。

## 🆕 新功能特性

### Docker-style 生命周期管理
- **`--rm` 模式**: 类似 `docker run --rm`，一步销毁并完全移除
- **分离的销毁/移除操作**: 支持先销毁（保留元数据）后清理的工作流
- **安全机制**: 支持强制模式和交互式确认

### 智能环境检测
- **自动检测现代/传统模式**: 优先使用现代 CLI，自动回退到传统方法
- **配置文件自动发现**: 支持 CONFIG、config.yml、config.yaml
- **环境验证**: 全面验证 CyRIS 安装和依赖

### 增强的用户体验
- **彩色输出**: 直观的状态指示（信息/成功/警告/错误）
- **干运行模式**: 安全预览将要执行的操作
- **详细进度**: 实时显示处理进度和成功率
- **优雅中断**: 支持 Ctrl+C 安全中断

## 🔧 使用方法

### 基本用法
```bash
# 交互式销毁所有靶场（推荐）
./destroy_all_cr.sh /home/cyuser/cyris/

# 查看帮助
./destroy_all_cr.sh --help

# 干运行模式（安全预览）
./destroy_all_cr.sh --dry-run /home/cyuser/cyris/
```

### 高级用法
```bash
# 强制销毁并完全移除所有痕迹
./destroy_all_cr.sh --force --rm /home/cyuser/cyris/

# 使用传统方法（兼容旧版本）
./destroy_all_cr.sh --legacy /home/cyuser/cyris/ CONFIG

# 详细输出模式
./destroy_all_cr.sh --verbose --dry-run /home/cyuser/cyris/
```

## 📋 命令行选项

| 选项 | 说明 |
|------|------|
| `-f, --force` | 强制执行，跳过确认提示 |
| `-r, --rm` | 销毁后完全移除所有记录（类似 docker run --rm） |
| `-n, --dry-run` | 干运行模式，显示将要执行的操作但不实际执行 |
| `-l, --legacy` | 使用传统销毁方法而非现代 CLI |
| `-v, --verbose` | 启用详细输出 |
| `-h, --help` | 显示帮助信息 |

## 🏗️ 工作原理

### 现代模式（默认）
1. **范围发现**: 使用 `cyris list --all` 获取所有靶场
2. **备选扫描**: 如果 CLI 无结果，扫描文件系统目录
3. **批量处理**: 对每个靶场执行 `cyris destroy [--force] [--rm] <range_id>`
4. **系统清理**: 清理临时文件、日志和孤立的 VM

### 传统模式（兼容性）
1. **文件系统扫描**: 扫描 `RANGE_DIRECTORY` 下的所有目录
2. **脚本执行**: 运行 `*whole-controlled*.sh` 清理脚本
3. **目录删除**: 删除范围目录和相关文件
4. **设置清理**: 清理 `settings/*.txt` 文件

## 🔄 与新架构的集成

### Docker-style 命令映射
- **destroy**: 停止 VM，清理资源，保留元数据（状态变为"destroyed"）
- **destroy --rm**: 一步完成销毁和移除
- **rm**: 完全移除销毁的靶场的所有痕迹

### 磁盘管理策略
- 支持新的范围特定磁盘组织 (`range/{id}/disks/`)
- 兼容传统磁盘位置
- 自动检测和清理两种文件组织方式

### 安全机制
- 强制模式需要显式 `--force` 标志
- 交互式确认（除非使用 `--force`）
- 干运行模式安全预览
- 优雅的信号处理（Ctrl+C）

## 📊 输出示例

### 成功运行示例
```
ℹ️  INFO: Starting destroy_all_cr.sh v2.0.0
ℹ️  INFO: Validating CyRIS environment...
✅ SUCCESS: Environment validation passed
ℹ️  INFO: Using modern CyRIS CLI interface
ℹ️  INFO: Scanning for cyber ranges...
⚠️  WARNING: Found 3 cyber ranges to destroy:
  - range_123
  - test_range
  - demo_env

Are you sure you want to destroy ALL these ranges? [y/N]: y

ℹ️  INFO: Processing range 1/3: range_123
ℹ️  INFO: Destroying range range_123 using modern CLI...
✅ SUCCESS: Range range_123 processed successfully

ℹ️  INFO: Processing range 2/3: test_range
ℹ️  INFO: Destroying range test_range using modern CLI...
✅ SUCCESS: Range test_range processed successfully

ℹ️  INFO: Processing range 3/3: demo_env
ℹ️  INFO: Destroying range demo_env using modern CLI...
✅ SUCCESS: Range demo_env processed successfully

ℹ️  INFO: Processing complete: 3/3 ranges processed successfully
ℹ️  INFO: Cleaning up system resources...
ℹ️  INFO: Cleaned up temporary setting files in /home/cyuser/cyris/settings
ℹ️  INFO: Cleaned up old log files in /home/cyuser/cyris/logs
✅ SUCCESS: All operations completed successfully!
```

### 干运行示例
```
ℹ️  INFO: DRY RUN MODE - No actual changes will be made
⚠️  WARNING: Found 2 cyber ranges to destroy:
  - range_456
  - staging_env
ℹ️  INFO: Processing range 1/2: range_456
ℹ️  INFO: Would execute: /home/cyuser/cyris/cyris destroy --force --rm range_456
ℹ️  INFO: Processing range 2/2: staging_env
ℹ️  INFO: Would execute: /home/cyuser/cyris/cyris destroy --force --rm staging_env
ℹ️  INFO: Would clean up temporary files and orphaned resources
ℹ️  INFO: Dry run completed - no actual changes were made
```

## 🔄 向后兼容性

### 与传统脚本的差异
| 特性 | 传统版本 | 现代版本 |
|------|----------|----------|
| 参数处理 | 位置参数 | 标准选项解析 |
| 错误处理 | 基础 | 全面的错误处理和验证 |
| 输出格式 | 简单文本 | 彩色、结构化输出 |
| 安全性 | 基本确认 | 多层安全机制 |
| 预览模式 | 无 | 干运行模式 |

### 迁移指南
```bash
# 传统用法
./destroy_all_cr.sh /path/to/cyris /path/to/CONFIG

# 现代等效用法
./destroy_all_cr.sh /path/to/cyris                    # 自动检测配置
./destroy_all_cr.sh --legacy /path/to/cyris /path/to/CONFIG  # 强制传统模式
```

## 🐛 故障排除

### 常见问题

**1. "Modern CLI not found" 警告**
- 脚本会自动回退到传统模式
- 确保 `cyris` 脚本存在且可执行

**2. "No ranges found" 消息**
- 正常情况，表示没有需要清理的靶场
- 可以用 `cyris list --all` 手动验证

**3. 权限错误**
- 确保脚本有执行权限: `chmod +x destroy_all_cr.sh`
- 确保对靶场目录有读写权限

**4. 孤立 VM 检测**
- 脚本会检测并报告孤立的 KVM 虚拟机
- 使用提供的 `virsh` 命令手动清理

### 调试模式
```bash
# 启用详细输出
./destroy_all_cr.sh --verbose --dry-run /path/to/cyris

# 查看实际执行的命令
bash -x ./destroy_all_cr.sh --dry-run /path/to/cyris
```

## 🔧 定制和扩展

### 环境变量支持
脚本支持以下环境变量（未来版本）：
- `CYRIS_DEFAULT_PATH`: 默认 CyRIS 路径
- `CYRIS_FORCE_LEGACY`: 强制使用传统模式
- `CYRIS_NO_COLOR`: 禁用彩色输出

### 钩子支持
可以通过以下方式扩展脚本：
- 在靶场目录中放置 `pre-destroy.sh` 和 `post-destroy.sh` 钩子
- 修改 `cleanup_system()` 函数添加自定义清理逻辑

## 📈 性能优化

### 并行处理（未来版本）
- 支持并行销毁多个靶场
- 可配置的并发级别
- 进度条显示

### 增量清理
- 智能检测需要清理的资源
- 跳过已经清理的范围
- 缓存靶场状态以提高性能

## 🔗 相关命令

### 单个靶场管理
```bash
# 销毁单个靶场（保留元数据）
cyris destroy range_123

# 销毁并移除单个靶场
cyris destroy --rm range_123

# 移除已销毁的靶场
cyris rm range_123

# 强制移除活跃靶场
cyris rm --force range_123
```

### 状态查询
```bash
# 列出所有靶场
cyris list --all

# 查看特定靶场状态
cyris status range_123

# 显示配置信息
cyris config-show
```

---

**注意**: 这个脚本是基于新的 Docker-style 生命周期管理系统构建的，提供了比传统脚本更安全、更灵活、更用户友好的批量清理功能。建议在生产环境使用前先通过 `--dry-run` 模式验证操作。