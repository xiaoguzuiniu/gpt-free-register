# -*- coding: utf-8 -*-
"""包装层：跑 test_codex_oauth --email，输出 tee 到文件。"""
import sys
sys.path.insert(0, r"D:\devApp\GPT协议注册-0419")

OUT_FILE = r"D:\devApp\GPT协议注册-0419\tools\_codex_relogin.out"

class Tee:
    def __init__(self, *streams):
        self.streams = streams
    def write(self, data):
        for s in self.streams:
            try: s.write(data); s.flush()
            except Exception: pass
    def flush(self):
        for s in self.streams:
            try: s.flush()
            except Exception: pass

f = open(OUT_FILE, "w", encoding="utf-8")
sys.stdout = Tee(sys.stdout, f)
sys.stderr = Tee(sys.stderr, f)

sys.argv = ["test_codex_oauth.py", "--email", "JeanineWetzler930@outlook.com"]

try:
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "test_codex_oauth",
        r"D:\devApp\GPT协议注册-0419\tools\test_codex_oauth.py",
    )
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    rc = m.main()
    print(f"\n[exit code = {rc}]", flush=True)
    f.write(f"\n[exit code = {rc}]")
except Exception as e:
    import traceback
    print(f"\n[顶层异常] {type(e).__name__}: {e}")
    traceback.print_exc()
finally:
    f.close()
