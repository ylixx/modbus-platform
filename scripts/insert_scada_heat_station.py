"""
将换热站监控 SCADA 组态页面写入数据库 (scada_pages 表)

绑定平台真实有数据的点位：
  - device_id=3 (明102, 在线, 数据持续写入)
    · 点位1 (Mpa, 压力) / 点位2 (热量/频率) / 点位3 (℃, 温度) / 点位4 (m³/h, 流量)
  静态回退值 = 运行时查询该点位最新缩放值；WS 连上后由实时值覆盖。

maotu 引擎图元规则（已逐项核对源码与“石化工艺演示”页面）：
  - Vue 组件： type='vue'，tag 为已注册组件名；props 必须为【原始值】（引擎自己包 {val}）。
  - 工业图元： type='svg'，tag 为 chem-*（chemicalSymbols.ts 37 个）；props={} 空。
  - 自由管线： type='sys-line'，tag 必须为 'sys-line'；point_position 为【画布绝对坐标】。
  - 每个图元都必须带 tag（缺失 tag → useExportJsonToDoneJson 按 id 找不到符号 → 整页空白）。

布局原则（避免“乱”）：
  - 供水主管 / 回水主管 作为两条水平主带（y=300 / y=820），设备分置其上/下方带区，用短接管连到主管。
  - 符号尺寸统一：泵 84×84、换热器 72×150、贮罐 170×82、风机 56×56、阀门 46×22、仪表见下。
  - 数据读数集中放进左侧“数据报表”面板，避免散落覆盖设备。
  - 阀门沿主管布置（P&ID 语义上阀门就在管上），设备不与主管重叠。

用法: python insert_scada_heat_station.py
"""
import json
import sqlite3
import sys
from datetime import datetime

DB_PATH = r"E:\zigbee\modbus-platform\backend\modbus_platform.db"
TARGET_DEVICE_ID = 3


def get_device_latest():
    conn = sqlite3.connect(DB_PATH)
    result = {}
    try:
        rows = conn.execute(
            """
            SELECT dt.name, dt.scale_factor, dt.decimal_places,
              (SELECT value FROM tag_history th WHERE th.tag_id=dt.id ORDER BY recorded_at DESC LIMIT 1) as raw
            FROM device_tags dt
            WHERE dt.device_id=?
            """,
            (TARGET_DEVICE_ID,),
        ).fetchall()
        for name, scale, dec, raw in rows:
            if raw is None:
                result[name] = 0.0
            else:
                val = float(raw) * (scale or 1.0)
                result[name] = round(val, dec if dec else 2)
    finally:
        conn.close()
    return result


def build_config():
    uid_seq = [0]

    def uid(p='item'):
        uid_seq[0] += 1
        return f"{p}_{datetime.now().strftime('%H%M%S')}_{uid_seq[0]:03x}"

    latest = get_device_latest()
    v_press = latest.get('点位1', 0.0)
    v_heat = latest.get('点位2', 0.0)
    v_temp = latest.get('点位3', 0.0)
    v_flow = latest.get('点位4', 0.0)

    S_PRESS = f"{TARGET_DEVICE_ID}:点位1"
    S_HEAT = f"{TARGET_DEVICE_ID}:点位2"
    S_TEMP = f"{TARGET_DEVICE_ID}:点位3"
    S_FLOW = f"{TARGET_DEVICE_ID}:点位4"

    C = {
        'bg': '#080f1e', 'panel': '#0d1526', 'panelLight': '#0a1322',
        'panelBorder': '#1e3a5f', 'accent': '#00d4ff', 'text': '#c8d4e8',
        'textBright': '#e8f0ff', 'textMuted': '#607896', 'ok': '#44cc88',
        'warn': '#ffaa00', 'danger': '#ff4466', 'pipe': '#00aaff',
    }
    COMMON_ANIM = {'val': '', 'delay': 'delay-0s', 'speed': 'slow', 'repeat': 'infinite'}
    EVENTS = []
    items = []

    def base(title, type_, tag, binfo, props=None, extra=None):
        it = {
            'id': uid(), 'title': title, 'type': type_, 'tag': tag,
            'binfo': {'left': binfo[0], 'top': binfo[1], 'width': binfo[2], 'height': binfo[3], 'angle': 0},
            'resize': True, 'rotate': True, 'lock': False, 'hide': False, 'active': False,
            'common_animations': COMMON_ANIM, 'events': EVENTS,
            'props': props or {},
        }
        if extra:
            it.update(extra)
        return it

    def panel(x, y, w, h, bg=None, shadow='always'):
        return base('面板', 'vue', 'card-vue', (x, y, w, h), {
            'shadow': shadow,
            'backGroundColor': bg or C['panel'],
            'boxShadow': 'rgba(0,0,0,0.45)',
        })

    def pipe(abs_pts, color=None, width=8, animated=True):
        xs = [p[0] for p in abs_pts]
        ys = [p[1] for p in abs_pts]
        pad = width / 2 + 2
        left = min(xs) - pad
        top = min(ys) - pad
        right = max(xs) + pad
        bottom = max(ys) + pad
        return base('管道', 'sys-line', 'sys-line', (left, top, right - left, bottom - top), {
            'stroke': color or C['pipe'],
            'stroke-width': width,
            'marker-start': False,
            'marker-end': False,
            'point_position': [{'x': p[0], 'y': p[1]} for p in abs_pts],
            'ani_type': 'electricity' if animated else 'none',
            'ani_dur': 20,
            'ani_color': '#00e676',
            'ani_reverse': False,
            'ani_play': animated,
            'bind_anchors': {'start': None, 'end': None},
        }, extra={'resize': True, 'rotate': True})

    def svg_item(tag, x, y, w, h, signal=None):
        it = base(tag, 'svg', tag, (x, y, w, h), {})
        if signal:
            it['device_bind'] = {'signalId': signal, 'attr': 'fill'}
        items.append(it)
        return it

    def kv(x, y, w, h, label, value, unit, signal=None, color=None):
        it = base(label, 'vue', 'kv-vue', (x, y, w, h), {
            'label': f'{label}({unit})' if unit else label,
            'value': f'{value}',
            'labelWidth': 110,
            'valueWidth': 80,
            'fontSize': 13,
            'color': color or C['accent'],
            'border': True,
            'borderColor': C['panelBorder'],
            'fontFamily': '黑体',
        })
        if signal:
            it['device_bind'] = {'signalId': signal, 'attr': 'value'}
        return it

    def txt(x, y, w, h, text, size=15, color=None, weight=700):
        it = base(text, 'vue', 'text-vue', (x, y, w, h), {
            'text': text, 'fontSize': size, 'fill': color or C['text'],
            'fontFamily': '黑体', 'vertical': False,
        })
        items.append(it)
        return it

    def btn(x, y, w, h, text, btype='success'):
        return base(text, 'vue', 'sys-button-vue', (x, y, w, h), {
            'text': text, 'type': btype, 'round': False,
        })

    # ───────────────────────── 面板框架 ─────────────────────────
    items.append(panel(10, 8, 1880, 64, '#0a1628'))        # 标题栏
    items.append(panel(10, 80, 340, 988))                   # 左侧主面板
    items.append(panel(360, 80, 1180, 988, C['panelLight']))# 中央工艺区
    items.append(panel(1550, 80, 360, 520))                 # 右侧设备状态
    # 左侧子面板
    items.append(panel(20, 96, 320, 200, C['panelLight']))  # 历史趋势
    items.append(panel(20, 322, 320, 180, C['panelLight'])) # 能耗排名
    items.append(panel(20, 518, 320, 180, C['panelLight'])) # 效率统计
    items.append(panel(20, 714, 320, 340, C['panelLight'])) # 数据报表

    # ───────────────────────── 主管 + 接管 ─────────────────────────
    Y_SUPPLY, Y_RETURN = 300, 820
    X0, X1 = 400, 1500
    items.append(pipe([(X0, Y_SUPPLY), (X1, Y_SUPPLY)], width=10))   # 供水主管
    items.append(pipe([(X0, Y_RETURN), (X1, Y_RETURN)], width=10))   # 回水主管
    stubs = [
        (472, 264, 472, Y_SUPPLY), (676, 270, 676, Y_SUPPLY),
        (896, 270, 896, Y_SUPPLY), (1185, 232, 1185, Y_SUPPLY),
        (562, Y_RETURN, 562, 864), (742, Y_RETURN, 742, 864),
        (942, Y_RETURN, 942, 864), (1235, Y_RETURN, 1235, 864),
    ]
    for (x1, y1, x2, y2) in stubs:
        items.append(pipe([(x1, y1), (x2, y2)], width=8))

    # ───────────────────────── 设备（上带=供水侧 / 下带=回水侧）─────────────────────────
    # 泵（S_FLOW）
    svg_item('chem-pump-centrifugal', 430, 180, 84, 84, S_FLOW)   # 自洗井泵（上）
    svg_item('chem-pump-centrifugal', 520, 880, 84, 84, S_FLOW)   # 深井泵（下）
    svg_item('chem-pump-centrifugal', 700, 880, 84, 84, S_FLOW)   # 补水泵（下）
    svg_item('chem-pump-centrifugal', 900, 880, 84, 84, S_FLOW)   # 排水泵（下）
    # 板式换热器（S_TEMP）
    svg_item('chem-hex-plate', 640, 120, 72, 150, S_TEMP)         # 1#换热器
    svg_item('chem-hex-plate', 860, 120, 72, 150, S_TEMP)         # 2#换热器
    # 贮罐（S_PRESS）
    svg_item('chem-tank-horizontal', 1100, 150, 170, 82, S_PRESS) # 补水箱（上）
    svg_item('chem-tank-horizontal', 1150, 880, 170, 82, S_PRESS)# 集水池（下）
    # 鼓风机/电机（S_HEAT）— 上带空隙布置
    for (x, y) in [(560, 150), (770, 150), (1000, 150), (1340, 160)]:
        svg_item('chem-blower', x, y, 56, 56, S_HEAT)

    # 阀门（沿主管布置，P&ID 语义即在管上）
    for x in [540, 660, 760, 1000, 1300, 1460]:
        svg_item('chem-valve-ball', x - 23, Y_SUPPLY - 11, 46, 22)
    for x in [460, 860, 1280]:
        svg_item('chem-valve-ball', x - 23, Y_RETURN - 11, 46, 22)

    # 就地仪表（靠近相关设备，不与设备/主管重叠）
    svg_item('chem-pressure-gauge', 410, 270, 50, 50, S_PRESS)   # 泵出口压力（泵左下方，零重叠）
    svg_item('chem-flow-meter', 360, 285, 50, 30, S_FLOW)        # 供水流量
    svg_item('chem-thermometer', 600, 248, 34, 68, S_TEMP)       # 换热器温度
    svg_item('chem-level-gauge', 1280, 158, 34, 68, S_PRESS)     # 水箱液位
    svg_item('chem-indicator', 470, 884, 36, 36, S_HEAT)         # 深井泵状态

    # ───────────────────────── 设备位号文字（居中带区空隙）─────────────────────────
    txt(430, 158, 120, 18, '自洗井泵', 12, C['textBright'])
    txt(640, 100, 120, 18, '1#换热器', 12, C['textBright'])
    txt(860, 100, 120, 18, '2#换热器', 12, C['textBright'])
    txt(1100, 128, 170, 18, '补水箱', 12, C['textBright'])
    txt(520, 968, 120, 18, '深井泵', 12, C['textBright'])
    txt(700, 968, 120, 18, '补水泵', 12, C['textBright'])
    txt(900, 968, 120, 18, '排水泵', 12, C['textBright'])
    txt(1150, 968, 170, 18, '集水池', 12, C['textBright'])

    # ───────────────────────── 左侧面板文字与读数 ─────────────────────────
    txt(20, 100, 160, 24, '历史趋势', 15, C['accent'])
    txt(36, 210, 280, 28, '温度 / 流量实时趋势', 12, C['textMuted'])
    txt(20, 326, 160, 24, '能耗排名', 15, C['accent'])
    txt(20, 522, 160, 24, '效率统计', 15, C['danger'])
    txt(36, 700, 280, 28, '当前在线设备 4 / 4', 12, C['textMuted'])
    txt(20, 718, 160, 24, '数据报表', 15, C['accent'])

    # 能耗排名 3 行
    for idx, (label, value, unit, color) in enumerate([
        ('供热面积', '68.2', 'm²', C['danger']),
        ('热负荷', '63.3', 'kW', C['warn']),
        ('供热量', '66.1', 'GJ', C['accent']),
    ]):
        y = 344 + idx * 32
        items.append(kv(30, y, 290, 28, label, value, unit, None, color))

    # 效率统计：换热效率 + 循环效率 + 报警状态
    txt(36, 540, 280, 24, '实时换热效率 92.3%', 13, C['ok'])
    items.append(kv(30, 580, 290, 28, '循环效率', round(v_heat, 1), 'Hz', S_HEAT, C['accent']))
    items.append(kv(30, 618, 290, 28, '报警状态', '正常', '', None, C['ok']))

    # 数据报表：10 个实时读数列表
    report = [
        ('供水压力', round(v_press, 1), 'MPa', S_PRESS),
        ('回水压力', round(v_press, 1), 'MPa', S_PRESS),
        ('供水温度', round(v_temp, 1), '°C', S_TEMP),
        ('回水温度', round(v_temp, 1), '°C', S_TEMP),
        ('瞬时流量', round(v_flow, 1), 'm³/h', S_FLOW),
        ('瞬时热量', round(v_heat, 1), 'GJ', S_HEAT),
        ('电频率', round(v_heat, 1), '%', S_HEAT),
        ('补水箱水位', round(v_flow, 1), '%', S_FLOW),
        ('集水池液位', round(v_press, 1), '%', S_PRESS),
    ]
    for i, (label, value, unit, sig) in enumerate(report):
        items.append(kv(30, 738 + i * 34, 290, 30, label, value, unit, sig))

    # ───────────────────────── 标题栏 / 时钟 / 按钮 ─────────────────────────
    txt(700, 18, 520, 40, '换热站监控系统', 28, C['danger'], 800)
    items.append(base('实时时钟', 'vue', 'now-time-vue', (24, 16, 200, 44), {
        'fontColor': C['accent'], 'timeSize': 22, 'dateSize': 11, 'weekSize': 11,
    }))
    items.append(btn(1600, 16, 140, 44, '自动运行', 'success'))
    items.append(btn(1750, 16, 120, 44, '手动', 'info'))

    # ───────────────────────── 右侧循环泵状态卡片 ─────────────────────────
    txt(1565, 92, 200, 24, '循环泵状态', 15, C['danger'])
    for idx, (name, status, color, bt) in enumerate([
        ('NO.1循环泵', '运行', C['ok'], 'success'),
        ('NO.2循环泵', '运行', C['ok'], 'success'),
        ('NO.1补水泵', '停止', C['warn'], 'info'),
        ('NO.2补水泵', '停止', C['warn'], 'info'),
    ]):
        y = 126 + idx * 92
        items.append(panel(1565, y, 330, 78, '#0f1d33'))
        txt(1580, y + 26, 170, 24, name, 13, C['textBright'])
        txt(1780, y + 26, 60, 24, status, 13, color)
        items.append(btn(1828, y + 22, 44, 34, '开' if status == '运行' else '关', bt))

    config = {
        '__engine': 'maotu',
        'canvasCfg': {
            'width': 1920, 'height': 1080, 'scale': 1,
            'color': C['bg'], 'img': '', 'guide': True,
            'adsorp': True, 'adsorp_diff': 3,
            'transform_origin': {'x': 0, 'y': 0}, 'drag_offset': {'x': 0, 'y': 0},
        },
        'gridCfg': {'enabled': True, 'align': True, 'size': 10},
        'json': items,
    }
    return config, latest


# ── 校验：复刻 useExportJsonToDoneJson 的崩溃条件 ──────────────────
CHEM_IDS = [
    'chem-tank-floating', 'chem-tank-sphere', 'chem-tank-conical', 'chem-tank-horizontal',
    'chem-pump-centrifugal', 'chem-pump-gear', 'chem-pump-vacuum',
    'chem-valve-gate', 'chem-valve-ball', 'chem-valve-butterfly', 'chem-valve-check',
    'chem-valve-control', 'chem-valve-motor', 'chem-valve-solenoid', 'chem-valve-relief',
    'chem-column-tray', 'chem-column-packed', 'chem-hex-shelltube', 'chem-hex-plate',
    'chem-hex-airaircooled', 'chem-hex-condenser', 'chem-compressor', 'chem-compressor-recip',
    'chem-blower', 'chem-sep-knockout', 'chem-sep-scrubber', 'chem-reactor', 'chem-furnace',
    'chem-cooler', 'chem-ejector', 'chem-vessel-h', 'chem-vessel-dome', 'chem-indicator',
    'chem-flow-meter', 'chem-thermometer', 'chem-pressure-gauge', 'chem-level-gauge',
]
SYMBOL_DEFAULT_PROPS = {
    'sys-line': {'stroke', 'stroke-width', 'marker-start', 'marker-end', 'point_position',
                 'ani_type', 'ani_dur', 'ani_color', 'ani_reverse', 'ani_play', 'bind_anchors'},
    'card-vue': {'shadow', 'backGroundColor', 'boxShadow'},
    'text-vue': {'text', 'fontFamily', 'fontSize', 'fill', 'vertical'},
    'now-time-vue': {'fontColor', 'dateSize', 'weekSize', 'timeSize'},
    'kv-vue': {'border', 'fontFamily', 'fontSize', 'label', 'labelWidth', 'value',
               'valueWidth', 'color', 'borderColor'},
    'sys-button-vue': {'text', 'type', 'round'},
}
for _cid in CHEM_IDS:
    SYMBOL_DEFAULT_PROPS[_cid] = set()


def validate(config):
    errors = []
    for it in config.get('json', []):
        tag = it.get('tag')
        title = it.get('title', '?')
        if tag not in SYMBOL_DEFAULT_PROPS:
            errors.append(f"[{title}] tag='{tag}' 未注册（type={it.get('type')}）—— 会导致整页空白")
            continue
        defaults = SYMBOL_DEFAULT_PROPS[tag]
        for k in it.get('props', {}):
            if k not in defaults:
                errors.append(f"[{title}] prop '{k}' 不在符号 '{tag}' 的默认属性中")
        for k, v in it.get('props', {}).items():
            if isinstance(v, dict) and set(v.keys()) == {'val'}:
                errors.append(f"[{title}] prop '{k}' 仍是包裹格式 {{'val':...}}，必须写成原始值")
    return errors


def main():
    NAME = '换热站监控系统（示例）'
    config, latest = build_config()
    config_json = json.dumps(config, ensure_ascii=False)

    errors = validate(config)
    if errors:
        print("❌ 配置校验未通过，已中止写入：", file=sys.stderr)
        for e in errors:
            print("   -", e, file=sys.stderr)
        sys.exit(1)
    print(f"✅ 配置校验通过：{len(config['json'])} 个图元，tag 全部已注册，props 均为原始值")

    print(f"📊 绑定目标设备: device_id={TARGET_DEVICE_ID} (明102, 在线)")
    print(f"   实时最新值: 压力={latest.get('点位1')} | 热量/频率={latest.get('点位2')} | "
          f"温度={latest.get('点位3')}℃ | 流量={latest.get('点位4')}m³/h")

    desc = ('基于 maotu 引擎的换热站 SCADA 组态示例页面，模仿经典 HMI 风格布局。'
            '绑定点位：device_id=3（明102，在线）的点位1/点位2/点位3/点位4，'
            '实时值由 WebSocket 推送，静态回退为查询时最新历史值。')

    conn = sqlite3.connect(DB_PATH)
    try:
        cur = conn.cursor()
        cur.execute("SELECT id FROM scada_pages WHERE name=?", (NAME,))
        row = cur.fetchone()
        if row:
            page_id = row[0]
            cur.execute("""
                UPDATE scada_pages
                SET description=?, width=?, height=?, background=?, config_json=?, device_ids=?, updated_at=datetime('now')
                WHERE id=?
            """, (desc, 1920, 1080, '#080f1e', config_json, '[3]', page_id))
            print(f"\n♻️  已更新已有页面 (id={page_id})，图元数量: {len(config['json'])}")
        else:
            cur.execute("""
                INSERT INTO scada_pages (name, description, width, height, background, config_json, device_ids, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, datetime('now'), datetime('now'))
            """, (NAME, desc, 1920, 1080, '#080f1e', config_json, '[3]'))
            page_id = cur.lastrowid
            print(f"\n✅ SCADA 页面创建成功！(id={page_id})")
            print(f"   图元数量: {len(config['json'])}")
        conn.commit()
        print(f"\n📌 运行查看: /scada/m-view/{page_id}")
        print(f"   编辑页面: /scada/m-editor/{page_id}")
        return page_id
    except sqlite3.Error as e:
        print(f"❌ 数据库错误: {e}", file=sys.stderr)
        sys.exit(1)
    finally:
        conn.close()


if __name__ == '__main__':
    main()
