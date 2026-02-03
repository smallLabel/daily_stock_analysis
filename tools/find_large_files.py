# -*- coding: utf-8 -*-
"""
大文件检测工具
找出项目中需要重构的大文件（>500行）
"""

import os
from pathlib import Path
from typing import List, Tuple


def count_lines(file_path: str) -> int:
    """统计文件行数"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return len(f.readlines())
    except:
        return 0


def find_large_files(
    root_dir: str = ".",
    threshold: int = 500,
    exclude_dirs: List[str] = None
) -> List[Tuple[str, int]]:
    """
    查找大文件
    
    Args:
        root_dir: 搜索根目录
        threshold: 行数阈值
        exclude_dirs: 排除的目录列表
        
    Returns:
        [(文件路径, 行数), ...]
    """
    if exclude_dirs is None:
        exclude_dirs = ['.venv', '.git', '__pycache__', 'node_modules']
    
    large_files = []
    root_path = Path(root_dir)
    
    for py_file in root_path.rglob('*.py'):
        # 检查是否在排除目录中
        if any(excl in str(py_file) for excl in exclude_dirs):
            continue
            
        line_count = count_lines(str(py_file))
        if line_count > threshold:
            rel_path = py_file.relative_to(root_path)
            large_files.append((str(rel_path), line_count))
    
    # 按行数降序排序
    large_files.sort(key=lambda x: x[1], reverse=True)
    return large_files


def generate_report(large_files: List[Tuple[str, int]]) -> str:
    """生成Markdown报告"""
    if not large_files:
        return "✅ 所有文件都在 500 行以内，代码结构良好！"
    
    report = f"# 大文件检测报告\n\n"
    report += f"**检测时间**: {__import__('datetime').datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
    report += f"**发现 {len(large_files)} 个文件超过500行**\n\n"
    
    report += "## 📊 详细列表\n\n"
    report += "| 优先级 | 文件 | 行数 | 建议 |\n"
    report += "|--------|------|------|------|\n"
    
    for file_path, lines in large_files:
        if lines > 1500:
            priority = "🔴 P0"
        elif lines > 1000:
            priority = "🔴 P0"
        elif lines > 800:
            priority = "🟡 P1"
        else:
            priority = "🟢 P2"
        
        suggestion = "需要重构"
        if lines > 2000:
            suggestion = "**紧急重构**"
        elif lines > 1000:
            suggestion = "优先重构"
        
        report += f"| {priority} | `{file_path}` | {lines} | {suggestion} |\n"
    
    report += "\n## 🎯 重构建议\n\n"
    report += "1. 优先处理 P0 级别的文件（>1000行）\n"
    report += "2. 将大文件拆分为模块化的包结构\n"
    report += "3. 保持向后兼容性\n"
    report += "4. 参考 `docs/REFACTORING_PLAN.md`\n"
    
    return report


def main():
    """主函数"""
    print("🔍 正在扫描项目中的大文件...\n")
    
    large_files = find_large_files(threshold=500)
    
    # 打印到控制台
    if large_files:
        print(f"发现 {len(large_files)} 个文件超过500行：\n")
        for file_path, lines in large_files[:10]:  # 只显示前10个
            print(f"  📄 {file_path:<50} {lines:>5} 行")
        
        if len(large_files) > 10:
            print(f"\n  ... 还有 {len(large_files) - 10} 个文件未显示")
    else:
        print("✅ 所有文件都在 500 行以内！")
    
    # 生成报告文件
    report = generate_report(large_files)
    report_path = "docs/LARGE_FILES_REPORT.md"
    
    os.makedirs("docs", exist_ok=True)
    with open(report_path, 'w', encoding='utf-8') as f:
        f.write(report)
    
    print(f"\n📊 详细报告已保存到: {report_path}")


if __name__ == "__main__":
    main()
