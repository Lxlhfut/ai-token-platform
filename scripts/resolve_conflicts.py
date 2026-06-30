"""批量清理 Git 冲突标记，保留 HEAD 版本"""
import re
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
APP_DIR = PROJECT_ROOT / "app"

files_with_conflicts = [
    "config.py",
    "models.py", 
    "schemas.py",
    "database.py",
    "init_db.py",
    "routers/admin.py",
    "routers/user.py",
    "templates/index.html",
    "templates/dashboard.html",
    "templates/admin.html",
    "static/app.js",
    "static/style.css",
]

def resolve_conflicts(text: str) -> str:
    """Remove Git conflict markers, keeping HEAD version (between <<<<<<< HEAD and =======)"""
    pattern = re.compile(
        r'<<<<<<< HEAD\n(.*?)\n=======\n.*?\n>>>>>>> 9917b3d52cb41738996b4ce0f28b48cbbf2f6a03',
        re.DOTALL
    )
    
    prev = None
    while prev != text:
        prev = text
        text = pattern.sub(r'\1', text)
    
    return text

for rel_path in files_with_conflicts:
    filepath = APP_DIR / rel_path
    if not filepath.exists():
        print(f"⚠ 文件不存在: {filepath}")
        continue
    
    original = filepath.read_text(encoding="utf-8")
    resolved = resolve_conflicts(original)
    
    if original != resolved:
        filepath.write_text(resolved, encoding="utf-8")
        print(f"✅ 已修复: {rel_path}")
    else:
        print(f"✓  无需修复: {rel_path}")

print("\n完成！")
