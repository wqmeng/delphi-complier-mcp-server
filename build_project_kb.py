import sys
import os
import time
from pathlib import Path
from multiprocessing import freeze_support

sys.path.insert(0, 'C:/User/delphi-complier-mcp-server')
os.chdir('C:/User/delphi-complier-mcp-server')


def main():
    from src.services.knowledge_base.project_knowledge_base import ProjectKnowledgeBase

    project_path = r"C:\User\diandaxia"
    project_dir = Path(project_path)
    dproj_files = list(project_dir.glob("*.dproj"))

    if dproj_files:
        main_dproj = dproj_files[0]
        print(f"项目文件: {main_dproj}")
    else:
        print("未找到 .dproj")
        return

    print("开始构建...")
    start = time.time()

    pkb = ProjectKnowledgeBase(str(main_dproj))

    print("[1/2] 项目源码...")
    pkb.build_project_knowledge_base(force_rebuild=True)

    print("[2/2] 第三方库...")
    pkb.build_thirdparty_knowledge_base(force_rebuild=True)

    print(f"完成! 耗时: {time.time()-start:.1f}s")

    stats = pkb.get_statistics()
    print("统计:", stats)


if __name__ == '__main__':
    freeze_support()
    main()
