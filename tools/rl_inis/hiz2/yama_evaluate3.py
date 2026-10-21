"""Amendment 24: evaluate.py --env-json (EnvConfig overrides, e.g. {"v_lateral": 1.5}); default empty = unchanged.

    python3 yama_evaluate3.py PATH/TO/evaluate.py
"""
import re
import sys

p = sys.argv[1]
s = open(p, encoding='utf-8').read()


def rep(old, new):
    global s
    if new in s:
        return
    assert s.count(old) == 1, old
    s = s.replace(old, new)


rep("import argparse\nimport collections\nimport csv\n", "import argparse\nimport collections\nimport csv\nimport json\n")
rep("    ap.add_argument('--out', required=True)\n",
    "    ap.add_argument('--env-json', default='',\n"
    "                    help='amendment 24: EnvConfig overrides as JSON, as train.py (e.g. the lateral speed)')\n"
    "    ap.add_argument('--out', required=True)\n")
if "**json.loads(a.env_json" not in s:
    m = re.search(r"\n( +)if a\.land_hard is not None else \{\}\)\}\)\)\n", s)
    assert m, 'land_hard line not found'
    ind = m.group(1)
    s = (s[:m.start()] + "\n" + ind + "if a.land_hard is not None else {}),\n"
         + ind + "**json.loads(a.env_json or '{}')}))\n" + s[m.end():])
open(p, 'w', encoding='utf-8').write(s)
print('evaluate.py yamandi:', p)
