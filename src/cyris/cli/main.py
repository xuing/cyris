#!/usr/bin/env python3
"""
CyRIS 现代化命令行接口
支持新的现代化命令，同时保持向后兼容
"""
import sys
import click
from pathlib import Path
from typing import Optional
import logging

from ..config.parser import parse_modern_config, ConfigurationError
from ..config.settings import CyRISSettings


# 设置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


@click.group()
@click.option('--config', '-c', 
              type=click.Path(exists=True, path_type=Path),
              help='配置文件路径')
@click.option('--verbose', '-v', is_flag=True, help='详细输出')
@click.pass_context
def cli(ctx, config: Optional[Path], verbose: bool):
    """
    CyRIS - 现代化网络安全培训环境部署工具
    
    使用现代化的命令行接口管理网络靶场的创建、部署和管理。
    """
    # 设置日志级别
    if verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    # 初始化上下文
    ctx.ensure_object(dict)
    ctx.obj['verbose'] = verbose
    
    # 加载配置
    if config:
        try:
            settings = parse_modern_config(config)
            ctx.obj['config'] = settings
            if verbose:
                click.echo(f"已加载配置文件: {config}")
        except ConfigurationError as e:
            click.echo(f"配置文件错误: {e}", err=True)
            sys.exit(1)
    else:
        # 尝试从默认位置加载配置
        default_configs = [
            Path.cwd() / 'config.yml',
            Path.cwd() / 'config.yaml', 
            Path.cwd() / 'CONFIG'
        ]
        
        settings = None
        for config_path in default_configs:
            if config_path.exists():
                try:
                    settings = parse_modern_config(config_path)
                    if verbose:
                        click.echo(f"自动加载配置: {config_path}")
                    break
                except ConfigurationError:
                    continue
        
        if settings is None:
            # 使用默认配置
            settings = CyRISSettings()
            if verbose:
                click.echo("使用默认配置")
        
        ctx.obj['config'] = settings


@cli.command()
@click.argument('description_file', type=click.Path(exists=True, path_type=Path))
@click.option('--range-id', type=int, help='指定靶场ID')
@click.option('--dry-run', is_flag=True, help='预演模式，不实际创建')
@click.pass_context
def create(ctx, description_file: Path, range_id: Optional[int], dry_run: bool):
    """
    创建新的网络靶场
    
    DESCRIPTION_FILE: YAML格式的靶场描述文件
    """
    config: CyRISSettings = ctx.obj['config']
    verbose = ctx.obj['verbose']
    
    click.echo(f"创建网络靶场: {description_file}")
    
    if verbose:
        click.echo(f"配置: {config}")
        click.echo(f"靶场ID: {range_id or '自动分配'}")
    
    if dry_run:
        click.echo("预演模式 - 不会实际创建靶场")
        # TODO: 实现预演逻辑
        return
    
    # TODO: 实现靶场创建逻辑
    click.echo("靶场创建功能正在开发中...")
    click.echo("当前请使用传统接口: python main/cyris.py")


@cli.command()
@click.option('--range-id', type=int, help='靶场ID')
@click.option('--all', 'list_all', is_flag=True, help='显示所有靶场')
@click.pass_context
def list(ctx, range_id: Optional[int], list_all: bool):
    """列出网络靶场"""
    config: CyRISSettings = ctx.obj['config']
    
    if range_id:
        click.echo(f"显示靶场 {range_id} 的详细信息")
    elif list_all:
        click.echo("列出所有靶场")
    else:
        click.echo("列出活跃的靶场")
    
    # 检查靶场目录
    ranges_dir = config.cyber_range_dir
    if not ranges_dir.exists():
        click.echo(f"靶场目录不存在: {ranges_dir}")
        return
    
    # 列出现有靶场目录
    range_dirs = [d for d in ranges_dir.iterdir() if d.is_dir()]
    
    if not range_dirs:
        click.echo("未找到任何靶场")
        return
    
    click.echo(f"在 {ranges_dir} 中找到 {len(range_dirs)} 个靶场:")
    for range_dir in sorted(range_dirs):
        click.echo(f"  - {range_dir.name}")
        
        # 查找详细信息文件
        detail_files = list(range_dir.glob("range_details-*.yml"))
        if detail_files:
            click.echo(f"    详细信息: {detail_files[0].name}")


@cli.command()
@click.argument('range_id', type=int)
@click.option('--force', '-f', is_flag=True, help='强制删除，不询问确认')
@click.pass_context
def destroy(ctx, range_id: int, force: bool):
    """
    销毁指定的网络靶场
    
    RANGE_ID: 要销毁的靶场ID
    """
    config: CyRISSettings = ctx.obj['config']
    
    if not force:
        if not click.confirm(f'确定要销毁靶场 {range_id} 吗？'):
            click.echo('操作已取消')
            return
    
    click.echo(f"销毁靶场: {range_id}")
    
    # TODO: 实现销毁逻辑
    click.echo("靶场销毁功能正在开发中...")
    click.echo(f"当前请使用: main/range_cleanup.sh {range_id} CONFIG")


@cli.command()
@click.argument('range_id', type=int)
@click.pass_context
def status(ctx, range_id: int):
    """
    显示靶场状态
    
    RANGE_ID: 靶场ID
    """
    config: CyRISSettings = ctx.obj['config']
    
    click.echo(f"靶场 {range_id} 状态:")
    
    # 检查靶场目录是否存在
    range_dir = config.cyber_range_dir / str(range_id)
    
    if not range_dir.exists():
        click.echo(f"  状态: 不存在")
        return
    
    click.echo(f"  状态: 存在")
    click.echo(f"  目录: {range_dir}")
    
    # 查找相关文件
    detail_files = list(range_dir.glob("range_details-*.yml"))
    notification_files = list(range_dir.glob("range_notification-*.txt"))
    
    if detail_files:
        click.echo(f"  详细信息文件: {detail_files[0].name}")
    
    if notification_files:
        click.echo(f"  通知文件: {notification_files[0].name}")


@cli.command()
@click.pass_context
def config_show(ctx):
    """显示当前配置"""
    config: CyRISSettings = ctx.obj['config']
    
    click.echo("当前配置:")
    click.echo(f"  CyRIS路径: {config.cyris_path}")
    click.echo(f"  靶场目录: {config.cyber_range_dir}")
    click.echo(f"  网关模式: {'启用' if config.gw_mode else '禁用'}")
    
    if config.gw_account:
        click.echo(f"  网关账户: {config.gw_account}")
    if config.gw_mgmt_addr:
        click.echo(f"  网关管理地址: {config.gw_mgmt_addr}")
    if config.user_email:
        click.echo(f"  用户邮箱: {config.user_email}")


@cli.command()
@click.option('--output', '-o', type=click.Path(path_type=Path), 
              default='config.yml', help='输出配置文件路径')
@click.pass_context
def config_init(ctx, output: Path):
    """初始化默认配置文件"""
    if output.exists():
        if not click.confirm(f'配置文件 {output} 已存在，是否覆盖？'):
            click.echo('操作已取消')
            return
    
    # 创建默认配置
    from ..config.parser import create_default_config
    
    try:
        settings = create_default_config(output)
        click.echo(f"✅ 默认配置文件已创建: {output}")
        click.echo("请编辑配置文件以适应您的环境")
    except Exception as e:
        click.echo(f"❌ 创建配置文件失败: {e}", err=True)


@cli.command()
@click.pass_context
def validate(ctx):
    """验证环境配置和依赖"""
    click.echo("验证CyRIS环境...")
    
    config: CyRISSettings = ctx.obj['config']
    errors = 0
    
    # 检查路径
    if not config.cyris_path.exists():
        click.echo(f"❌ CyRIS路径不存在: {config.cyris_path}")
        errors += 1
    else:
        click.echo(f"✅ CyRIS路径: {config.cyris_path}")
    
    if not config.cyber_range_dir.exists():
        click.echo(f"❌ 靶场目录不存在: {config.cyber_range_dir}")
        errors += 1
    else:
        click.echo(f"✅ 靶场目录: {config.cyber_range_dir}")
    
    # 检查传统脚本
    legacy_script = config.cyris_path / 'main' / 'cyris.py'
    if legacy_script.exists():
        click.echo(f"✅ 传统脚本可用: {legacy_script}")
    else:
        click.echo(f"⚠️  传统脚本不可用: {legacy_script}")
    
    # 检查示例文件
    examples_dir = config.cyris_path / 'examples'
    if examples_dir.exists():
        try:
            example_files = list(examples_dir.glob('*.yml'))
            click.echo(f"✅ 示例文件: {len(example_files)} 个")
        except Exception as e:
            click.echo(f"⚠️  检查示例文件时出错: {e}")
    else:
        click.echo(f"⚠️  示例目录不存在: {examples_dir}")
    
    if errors == 0:
        click.echo("🎉 环境验证通过!")
    else:
        click.echo(f"❌ 发现 {errors} 个问题")
        sys.exit(1)


@cli.command(name='legacy')
@click.argument('args', nargs=-1)
@click.pass_context
def legacy_run(ctx, args):
    """
    运行传统CyRIS命令
    
    这是一个兼容性命令，会调用原始的main/cyris.py脚本
    """
    import subprocess
    
    config: CyRISSettings = ctx.obj['config']
    legacy_script = config.cyris_path / 'main' / 'cyris.py'
    
    if not legacy_script.exists():
        click.echo(f"❌ 传统脚本不存在: {legacy_script}", err=True)
        sys.exit(1)
    
    # 构建命令
    cmd = ['python3', str(legacy_script)] + list(args)
    
    if ctx.obj['verbose']:
        click.echo(f"执行命令: {' '.join(cmd)}")
    
    try:
        # 运行传统脚本
        result = subprocess.run(cmd, cwd=config.cyris_path)
        sys.exit(result.returncode)
    except KeyboardInterrupt:
        click.echo("\n操作被用户中断")
        sys.exit(1)
    except Exception as e:
        click.echo(f"❌ 执行失败: {e}", err=True)
        sys.exit(1)


def main():
    """主入口点"""
    try:
        cli()
    except KeyboardInterrupt:
        click.echo("\n操作被用户中断")
        sys.exit(1)
    except Exception as e:
        click.echo(f"❌ 未预期的错误: {e}", err=True)
        sys.exit(1)


if __name__ == '__main__':
    main()