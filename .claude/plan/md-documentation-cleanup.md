# MD文档整理执行计划

## 任务背景
整理根目录下散乱的11个MD文档，建立清晰的文档结构

## 分析结果
- **根目录MD文档**: 11个文件，约78KB
- **文档类型**: 实现总结(5) + 修复记录(4) + 项目文档(2)
- **现有docs结构**: analysis/, design/, guides/

## 采用方案
**Solution 1: 按文档类型分类归档法**

## 执行步骤

### Step 1: 创建目录结构
```bash
mkdir -p docs/{implementation,fixes,testing,migrations}
```

### Step 2: 文档移动和重命名
```bash
# Implementation documents
mv ENHANCED_KVM_AUTO_IMPLEMENTATION.md docs/implementation/enhanced-kvm-auto-implementation.md
mv ENHANCED_PTY_IMPLEMENTATION_SUMMARY.md docs/implementation/enhanced-pty-implementation-summary.md
mv FINAL_IMPLEMENTATION_SUMMARY.md docs/implementation/final-implementation-summary.md

# Bug fixes and issues
mv CRITICAL_BUG_FIXES_SUMMARY.md docs/fixes/critical-bug-fixes-summary.md
mv PARSING_FIX_SUMMARY.md docs/fixes/parsing-fix-summary.md
mv FINAL_SUBPROCESS_BUG_FIX.md docs/fixes/final-subprocess-bug-fix.md

# Testing documents
mv TESTING_RICH_PROGRESS.md docs/testing/testing-rich-progress.md
mv RICH_PROGRESS_TEST_RESULTS.md docs/testing/rich-progress-test-results.md

# Migration notes
mv PYDANTIC_V2_MIGRATION_NOTES.md docs/migrations/pydantic-v2-migration-notes.md
```

### Step 3: 保留根目录文档
```
根目录保留:
- README.md (项目主文档)
- CLAUDE.md (Claude Code工作指南)
```

### Step 4: 创建文档索引
在 `docs/README.md` 中创建导航索引

### Step 5: 验证链接和引用
检查移动后的文档是否有内部链接需要更新

## 预期结果
- 根目录从11个MD文档减少到2个核心文档
- docs目录按类型组织，便于查找和维护
- 保留所有历史记录和技术文档
- 建立清晰的文档导航体系

## 风险和缓解
- **链接失效**: 移动后检查内部引用
- **可访问性**: 通过docs索引提供导航
- **版本控制**: 使用git mv保持历史记录

## 执行时间估计
约15-20分钟完成所有步骤