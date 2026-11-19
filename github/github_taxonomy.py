# -*- coding: utf-8 -*-
"""GitHub 热点的「分析理解」引擎。

不搬运 star 数，而是回答四个问题：
  1) 这是不是真项目？（识别刷星投放、资源合集、纯 prompt 包）
  2) 它属于哪条技术路线？（topics + language + README 三源交叉）
  3) 它为什么现在火？（赛道星速基线对比，看是踩中趋势还是个体异常）
  4) 值不值得你动手？（成熟度打分 → 可直接用 / 看思路 / 只看热闹）

所有判定都输出依据，方便复核；不确定的一律标「疑似」，不假装确定。
"""
import re, datetime, statistics
from collections import Counter

# ---------------- 赛道定义 ----------------
TRACKS = [
    {
        'name': 'AI Agent 与自动化',
        'kw': ['agent', 'agentic', 'autonomous', 'mcp', 'multi-agent', 'workflow', 'automation',
               'orchestrat', 'tool-use', 'computer-use', 'copilot'],
        'frame': 'Agent 赛道的竞争点已经从「能不能调工具」转到「长任务能不能不崩」。'
                 '看这类项目只问三件事：状态怎么持久化、失败了怎么恢复、工具调用的权限边界在哪。',
        'judge': ['是否有持久化状态/断点恢复（不是每轮重来）',
                  '工具调用是否沙箱化、权限是否可收敛',
                  '长任务成功率有没有实测数据，而不是 demo 视频'],
    },
    {
        'name': '大模型工具链',
        'kw': ['llm', 'inference', 'training', 'fine-tun', 'quantiz', 'vllm', 'cuda', 'gpu',
               'transformer', 'tokeniz', 'embedding', 'rag', 'model', 'serving', 'harness'],
        'frame': '工具链项目的价值全在「同样的卡能不能多跑吞吐」。'
                 '不看 benchmark 数字，看它的优化手段属于哪一层：算子层、调度层还是显存管理。',
        'judge': ['优化发生在哪一层（kernel / 调度 / 显存 / 批处理）',
                  '对比基线是谁，测试负载是什么',
                  '是否依赖特定硬件或驱动版本'],
    },
    {
        'name': 'AI 生成内容',
        'kw': ['diffusion', 'image-gen', 'text-to-image', 'text-to-video', 'video-gen', 'tts',
               'voice', 'speech', 'stable-diffusion', 'comfyui', 'lora', 'avatar', 'clipping',
               'point cloud', 'scan', 'model-gen', 'texture'],
        'frame': '生成类项目的分水岭是「可控性」。能出图不算能力，能稳定复现同一张脸、同一套风格才算。',
        'judge': ['控制手段（ControlNet / LoRA / 参考图）是否完整',
                  '推理成本（单张/单秒要多少显存和时间）',
                  '是否只是套壳调用别人的 API'],
    },
    {
        'name': '开发工具与编辑器',
        'kw': ['ide', 'editor', 'vscode', 'cli', 'devtool', 'terminal', 'linter', 'formatter',
               'debug', 'compiler', 'language-server', 'code-review', 'coding',
               'codebase', 'understand how', 'software works'],
        'frame': '工具有个残酷规律：迁移成本决定生死。再好用，只要不能复用现有配置和工作流，就很难留下用户。',
        'judge': ['能否复用现有配置（插件/快捷键/主题）',
                  '启动速度与内存占用是否真的更优',
                  '生态缺口有多大（插件数量、语言支持）'],
    },
    {
        'name': '系统与底层',
        'kw': ['kernel', 'os', 'runtime', 'container', 'vm', 'emulator', 'recompil', 'firmware',
               'bootloader', 'driver', 'filesystem', 'embedded', 'rust', 'wasm', 'hypervisor',
               'cfw', 'mount', 'simulator', 'homebrew'],
        'frame': '底层项目的可信度看两件事：有没有可复现的构建、有没有处理失败路径。'
                 '这类项目 demo 容易、生产难，边界条件才是真功夫。',
        'judge': ['构建是否可复现（CI、依赖锁定）',
                  '错误处理与边界条件覆盖到什么程度',
                  '许可证是否允许商用（GPL 会限制落地）'],
    },
    {
        'name': '前端与界面',
        'kw': ['react', 'vue', 'svelte', 'ui', 'css', 'tailwind', 'nextjs', 'component',
               'animation', 'design-system', 'frontend', 'web', 'dynamic-island',
               'font', 'typeface', 'icon', 'layout'],
        'frame': '前端项目的生命周期由「设计系统契合度」决定。视觉再惊艳，接不进现有组件体系就只能当参考。',
        'judge': ['是否零依赖/低侵入，能否单独摘出来用',
                  '无障碍与键盘操作是否覆盖',
                  '包体积与运行时开销'],
    },
    {
        'name': '数据与检索',
        'kw': ['database', 'vector', 'search', 'index', 'sql', 'query', 'etl', 'pipeline',
               'analytics', 'dataframe', 'storage', 'cache'],
        'frame': '数据类项目的关键是「一致性模型」和「写入放大」。'
                 '参数漂亮但一致性语义模糊的项目，上线就会出数据问题。',
        'judge': ['一致性/事务语义是否说清楚',
                  '写入与查询的实际开销（不只是 QPS 峰值）',
                  '运维复杂度：要不要额外组件'],
    },
    {
        'name': '安全与逆向',
        'kw': ['security', 'vulnerab', 'exploit', 'pentest', 'malware', 'reverse', 'crack',
               'credential', 'privacy', 'sandbox', 'leak', 'protocol', '凭据', '逆向'],
        'frame': '安全工具要区分「研究」和「可用武器」。前者看披露质量，后者看稳定性和影响面。'
                 '这类项目同时受法律与技术双重约束。',
        'judge': ['技术手法是否可复现、有没有写清影响范围',
                  '是否已通知厂商/是否在野利用',
                  '使用是否触碰法律红线（授权、越权）'],
    },
    {
        'name': '桌面与效率应用',
        'kw': ['desktop', 'macos', 'windows', 'linux app', 'menu bar', 'launcher', 'note',
               'productivity', 'download', 'player', 'browser', 'wallpaper', 'tv'],
        'frame': '效率应用的天花板是「分发」。功能谁都能做，能不能装到用户机器上（签名、商店、权限）才是门槛。',
        'judge': ['安装与签名成本（是否要关 SIP / 装驱动）',
                  '跨平台一致性',
                  '数据是否本地存储（隐私）'],
    },
    {
        'name': '平台与基础设施',
        'kw': ['server', 'api', 'gateway', 'kubernetes', 'docker', 'deploy', 'proxy',
               'self-host', 'backend', 'microservice', 'queue'],
        'frame': '基础设施项目看「故障时的行为」。正常路径谁都能跑通，超时、重试、限流才是分水岭。',
        'judge': ['失败与超时处理是否明确',
                  '部署依赖有多少（一个容器能起还是五个）',
                  '可观测性：有没有指标和日志'],
    },
]

# ---------------- 需要过滤 / 降级的类型 ----------------
JUNK_RULES = [
    {
        'kind': '资源合集',
        'kw': ['awesome', 'roadmap', 'public-apis', 'build-your-own', 'free-programming',
               'cheatsheet', 'interview', 'curated list', 'collection of', 'list of',
               'tutorial', 'handbook', '学习路线', '面试题', '教程', '资源', '合集', '导航'],
        'why': '清单/合集类，价值在索引而非代码，属于二次整理搬运',
    },
    {
        'kind': '提示词包',
        'kw': ['skill pack', 'skills for', 'skill to', 'a skill for', 'prompt library', 'prompts for', 'prompt collection',
               '系统提示词', '提示词'],
        'why': '纯提示词/技能包，无工程实现，质量取决于写作而非代码',
    },
]


def _txt(r):
    parts = [r.get('name') or '', r.get('description') or '']
    parts += (r.get('topics') or [])
    return ' '.join(parts).lower()


def _norm_desc(r):
    """归一化描述用于查重：去 emoji、标点、大小写，只留字母数字与中文。"""
    d = (r.get('description') or '').lower()
    d = re.sub(r'[^0-9a-z\u4e00-\u9fff]+', '', d)
    return d[:120]


def detect_farm(repos):
    """识别刷星投放 / 克隆农场。

    实测：新星榜里出现过 21 个描述完全相同、fork 为 0 的 Makefile 仓库。
    但「描述相同」不能单独定罪——真实项目之间也会互相抄描述（如两个 Switch 2 模拟器
    描述一模一样，fork 却高达 1560 和 666）。因此加两道门槛：
      · 同描述 ≥3 个 → 批量投放（人手不可能自然产出 3 个同名同描述项目）
      · 同描述 =2 个 → 只有其中至少一个 fork 比 <0.02 才判克隆（真项目不会零 fork）
    """
    groups = {}
    for r in repos:
        k = _norm_desc(r)
        if k:
            groups.setdefault(k, []).append(r)

    farms = set()
    for k, rs in groups.items():
        if len(rs) >= 3:
            farms.add(k)
        elif len(rs) == 2:
            ratios = [(r.get('forks_count') or 0) / (r.get('stargazers_count') or 1) for r in rs]
            if min(ratios) < 0.02:
                farms.add(k)
    return farms


def classify(r):
    """返回 (赛道 dict 或 None, 命中词)。

    优先级：描述（作者自己写的定位）> topics。
    实测坑：有项目为了曝光把 agent / mcp 塞进 topics，但描述明明是「把应用重写成 Rust」，
    只按 topics 加权会把它误归到 AI 赛道。所以描述命中就用描述，描述没信息才看 topics。
    """
    topics = ' '.join(r.get('topics') or []).lower()
    desc = ((r.get('description') or '') + ' ' + (r.get('name') or '')).lower()

    best_desc, best_dh = None, []
    for t in TRACKS:
        h = [k for k in t['kw'] if k in desc]
        if len(h) > len(best_dh):
            best_desc, best_dh = t, h
    if best_desc:
        return best_desc, best_dh

    best_top, best_th = None, []
    for t in TRACKS:
        h = [k for k in t['kw'] if k in topics]
        if len(h) > len(best_th):
            best_top, best_th = t, h
    return best_top, best_th


def junk_check(r, farm_keys):
    """返回 (类型, 理由) 或 None。顺序：刷星 > 合集 > 提示词包。"""
    k = _norm_desc(r)
    if k in farm_keys:
        return '刷星投放', '同一段描述被多个仓库复用，且 fork 极低——典型批量刷星引流'
    txt = _txt(r)
    for rule in JUNK_RULES:
        hits = [w for w in rule['kw'] if w in txt]
        if hits:
            # 有真实代码语言的，降级为「带合集的代码项目」而不是直接判死
            if r.get('language') and len(hits) == 1 and hits[0] in ('tutorial', '教程'):
                continue
            return rule['kind'], f"{rule['why']}（命中：{'、'.join(hits[:3])}）"
    return None


def readme_signals(readme):
    """从 README 提取技术路线线索。返回 dict，全部是「有/无」事实，不做推断。"""
    if not readme:
        return {'install': [], 'stack': [], 'inherit': [], 'platform': [], 'has_code_block': False}
    low = readme.lower()
    install_map = {
        'pip': ['pip install', 'uv add', 'pipx'], 'npm': ['npm i', 'npm install', 'pnpm add', 'yarn add'],
        'cargo': ['cargo install', 'cargo add'], 'docker': ['docker run', 'docker compose', 'docker-compose'],
        'brew': ['brew install'], 'go': ['go install'], 'binary': ['download the release', 'prebuilt binary'],
    }
    install = [k for k, ws in install_map.items() if any(w in low for w in ws)]
    stack_map = {
        'Rust 实现': ['written in rust', 'rust-based', '用 rust'],
        'Tauri': ['tauri'], 'Electron': ['electron'], 'WASM': ['wasm', 'webassembly'],
        'llama.cpp': ['llama.cpp'], 'vLLM': ['vllm'], 'CUDA': ['cuda'],
        'PyTorch': ['pytorch', 'torch'], 'Swift 原生': ['swiftui', 'appkit'],
        'Kotlin/Android': ['kotlin', 'android sdk'], 'Flutter': ['flutter', 'dart'],
    }
    stack = [k for k, ws in stack_map.items() if any(w in low for w in ws)]
    inherit = [w for w in ('based on', 'built on top of', 'fork of', 'wrapper around',
                           'alternative to', 'reimplement', 'clean-room') if w in low]
    plat = [k for k, ws in {'macOS': ['macos', 'os x'], 'Windows': ['windows'],
                            'Linux': ['linux'], 'iOS': ['ios '], 'Android': ['android']}.items()
            if any(w in low for w in ws)]
    return {
        'install': install, 'stack': stack, 'inherit': inherit,
        'platform': plat, 'has_code_block': '```' in readme,
    }


def metrics(r, today=None):
    today = today or datetime.date.today()
    stars = r.get('stargazers_count') or 0
    forks = r.get('forks_count') or 0
    created = (r.get('created_at') or '')[:10]
    try:
        c = datetime.date.fromisoformat(created)
        age = max(1, (today - c).days)
    except Exception:
        age = 30
    return {
        'stars': stars,
        'forks': forks,
        'age': age,
        'velocity': stars / age,                 # 每天涨多少星
        'fork_ratio': forks / stars if stars else 0,
        'issue_ratio': (r.get('open_issues_count') or 0) / stars if stars else 0,
    }


def maturity(r, m, sig, junk):
    """成熟度 0-100 + 分项，用于给「能不能用」的结论。"""
    s = 0
    detail = []
    # 采用度（fork 比）30
    fr = m['fork_ratio']
    use = 30 if fr >= 0.25 else 24 if fr >= 0.12 else 16 if fr >= 0.05 else 8 if fr >= 0.02 else 0
    s += use
    detail.append(('真实使用度', use, f'fork/star = {fr:.3f}'))
    # 工程完整度（安装方式 + 代码块）25
    eng = min(25, len(sig['install']) * 7 + (6 if sig['has_code_block'] else 0))
    s += eng
    detail.append(('工程完整度', eng, '安装方式：' + ('、'.join(sig['install']) or 'README 未写明')))
    # 合规可用（license）20
    lic = (r.get('license') or {}).get('spdx_id') if r.get('license') else None
    ls = 20 if lic in ('MIT', 'Apache-2.0', 'BSD-3-Clause', 'ISC') else 12 if lic else 0
    s += ls
    detail.append(('许可证', ls, lic or '无 license（默认保留所有权利）'))
    # 产品化（homepage / release）15
    prod = 0
    if r.get('homepage'):
        prod += 8
    if sig['platform']:
        prod += 4
    if sig['stack']:
        prod += 3
    s += min(15, prod)
    detail.append(('产品化程度', min(15, prod), '有主页/平台说明' if prod else '无主页'))
    # 风险扣分
    if junk:
        s -= 25
        detail.append(('风险扣分', -25, f'{junk[0]}：{junk[1]}'))
    if m['fork_ratio'] < 0.02 and m['stars'] > 500:
        s -= 15
        detail.append(('风险扣分', -15, 'fork 极低而 star 很高，采用度与热度不匹配'))
    return max(0, min(100, s)), detail


def verdict(score, junk):
    if junk:
        return '只看热闹', '内容属二次整理/投放，不构成可直接复用的工程'
    if score >= 65:
        return '可直接用', '工程师信号齐全，建议直接跑一遍验证'
    if score >= 45:
        return '看思路', '有真实现但成熟度一般，值得读代码而非直接依赖'
    return '谨慎', '信号不足，先观察或只看设计取向'


def trend_note(track_name, items_in_track, all_items):
    """给赛道一句趋势判断：体量 + 星速是否高于全局中位。"""
    if not items_in_track:
        return ''
    vs = [i['m']['velocity'] for i in items_in_track]
    allv = [i['m']['velocity'] for i in all_items] or [0]
    med, gmed = statistics.median(vs), statistics.median(allv)
    ratio = med / gmed if gmed else 0
    if ratio >= 1.4:
        return f'本期吸星效率是全局的 {ratio:.1f} 倍，属于正在起势的赛道'
    if ratio >= 0.8:
        return f'吸星效率与全局持平（{ratio:.1f}×），是稳定赛道'
    return f'吸星效率低于全局（{ratio:.1f}×），本期不是风口'
