# FUXA SCADA 编辑器架构深度分析报告

> 基于 FUXA master 分支源码的完整逆向分析，用于指导 SCADA 编辑器从零重写

---

## 一、核心数据模型 (hmi.ts)

### 1.1 Hmi 顶层容器

```typescript
class Hmi {
    layout: LayoutSettings = new LayoutSettings();  // 导航菜单/头栏等布局配置
    views: View[] = [];                              // 画面列表
}
```

### 1.2 View 画面模型

```typescript
class View {
    id = '';                          // 随机ID, 格式 'v_' + shortGUID
    name = '';                        // 画面名称（作为引用标识）
    profile: DocProfile = new DocProfile();  // 画面尺寸/背景色
    items: DictionaryGaugeSettings = {};     // 🔑 核心中枢：图元配置字典
    variables: DictionaryVariables = {};    // 画面变量
    svgcontent = '';                  // SVG 字符串内容（完整SVG代码）
    type: ViewType;                   // 画面类型：svg | cards | maps
    property: ViewProperty;           // 画面级事件（Open/Close）
}
```

**关键设计**：
- `svgcontent` 存储整个画面的 SVG XML 字符串
- `items` 是 `{ [svgElementId]: GaugeSettings }` 字典，SVG 元素的 `id` 与 GaugeSettings 一一对应
- 这是"SVG 内容 + 元数据字典"的双层存储架构

### 1.3 GaugeSettings 图元配置

```typescript
class GaugeSettings {
    name = '';                // 图元实例名称（如 "button_1", "led_2"）
    property: any = null;     // GaugeProperty 或其子类
    label = '';               // 图元类型标签
    hide = false;             // 是否隐藏
    lock = false;             // 是否锁定
    constructor(public id: string, public type: string) {}
    // id = SVG元素的id属性值
    // type = SVG元素的type属性值，如 'svg-ext-value-xx', 'svg-ext-button-xx'
}
```

### 1.4 GaugeProperty 数据绑定基类

```typescript
class GaugeProperty {
    variableId: string;           // 绑定的Tag/信号ID
    variableValue: string;        // 静态初始值
    bitmask: number;              // 位掩码
    permission: number;           // 权限
    permissionRoles: PermissionRoles; // 角色权限
    ranges: GaugeRangeProperty[];     // 值域范围（颜色/文本映射）
    events: GaugeEvent[] = [];        // 鼠标/键盘事件
    actions: GaugeAction[] = [];      // 数据驱动动作
    options: any;                     // 组件特定选项
    readonly: boolean;
    text: string;                     // 文本属性（按钮用）
    icon?: string;                    // Material图标（按钮用）
    image?: string;                   // 图片资源（按钮用）
}
```

### 1.5 WidgetProperty 扩展

```typescript
class WidgetProperty extends GaugeProperty {
    type: string;                         // Widget类型标识
    scriptContent?: { moduleId: string, content: string };
    svgContent?: string;                  // 内嵌SVG内容
    varsToBind?: WidgetPropertyVariable[] = []; // 变量绑定列表
}
```

### 1.6 GaugeRangeProperty 值域映射

```typescript
class GaugeRangeProperty {
    min: number;          // 范围下限
    max: number;          // 范围上限
    text: string;         // 范围内显示文本
    textId: string;       // 动态文本的Tag引用
    color: string;        // 范围内填充色
    type: any;            // 属性类型
    style: any;           // 样式
    stroke: string;       // 范围内描边色
}
```

### 1.7 GaugeAction 数据驱动动作

```typescript
class GaugeAction {
    variableId: string;     // 关联的信号ID
    bitmask: number;        // 位掩码
    range: GaugeRangeProperty; // 触发范围
    type: any;              // 动作类型
    options: any = {};      // 动作参数
}

// 动作类型枚举
enum GaugeActionsType {
    hide, show, blink, color, stop,
    clockwise, anticlockwise, downup, rotate,
    move, moveByTags, monitor,
    refreshImage, loadImage, start, pause, reset
}
```

**关键动作参数**：
- `GaugeActionBlink`: fillA/B, strokeA/B, interval
- `GaugeActionRotate`: minAngle, maxAngle, delay
- `GaugeActionMove`: toX, toY, duration
- `GaugeActionMoveByTags`: axis, valueMin/Max, positionMin/Max, duration

### 1.8 GaugeEvent 鼠标/键盘事件

```typescript
class GaugeEvent {
    type: string;          // 事件类型（click, dblclick, mousedown等）
    action: string;        // 响应动作类型
    actparam: string;      // 动作参数（如view名称、URL）
    actoptions = <any>{};  // 动作选项
}

// 事件动作类型
enum GaugeEventActionType {
    onpage, onwindow, onOpenTab, ondialog, oniframe, oncard,
    onSetValue, onToggleValue, onSetInput, onclose,
    onRunScript, onViewToPanel, onMonitor
}
```

### 1.9 DocProfile 画面规格

```typescript
class DocProfile {
    width = 1024;
    height = 768;
    bkcolor = '#ffffffff';
    margin = 10;
    align = DocAlignType.topCenter;
    gridType: GridType = GridType.Fixed;
    viewRenderDelay = 0;  // 延迟渲染防闪烁
}
```

### 1.10 DictionaryGaugeSettings 类型定义

```typescript
interface DictionaryGaugeSettings {
    [x: string]: GaugeSettings;  // key = SVG元素id
}
```

---

## 二、编辑器架构 (editor.component.ts)

### 2.1 SVG-Edit 集成架构

FUXA **不自己实现 SVG 画布引擎**，而是深度封装了 **SVG-Edit**（一个成熟的开源 SVG 编辑器）。集成方式：

```typescript
// 通过全局变量（declare var）桥接 SVG-Edit 的 JS 库
declare var mypathseg: any;      // 路径段处理
declare var mybrowser: any;      // 浏览器兼容
declare var mysvgutils: any;     // SVG 工具
declare var myselect: any;       // 选择管理
declare var mydraw: any;         // 绘制管理
declare var mysvgcanvas: any;     // 画布核心
declare var mysvgeditor: any;     // 编辑器顶层

// 通过 WindowRef 访问全局 svgEditor 实例
this.winRef.nativeWindow.svgEditor
```

### 2.2 初始化流程

```typescript
private myInit() {
    // 1. 初始化 SVG-Edit 底层模块（顺序严格）
    mypathseg.initPathSeg();
    mybrowser.initBrowser();
    mysvgutils.initSvgutils();
    myselect.initSelect();
    mydraw.initDraw();
    mysvgcanvas.initSvgCanvas();

    // 2. 初始化 SVG-Edit 编辑器，传入 6 个回调
    mysvgeditor.initSvgEditor($,
        (selected) => { ... },       // onSelected: 选中元素回调
        (type, args) => { ... },     // onExtensionLoaded: 扩展加载回调
        (type, color) => { ... },    // onColorChanged: 颜色变更回调
        (eleadded) => { ... },       // onElementAdded: 元素添加回调
        (eleremoved) => { ... },     // onElementRemoved: 元素删除回调
        (eleresized) => { ... },     // onElementResized: 元素缩放回调
    );

    // 3. 触发 SVG-Edit 自身初始化
    this.winRef.nativeWindow.svgEditor.init();
}
```

### 2.3 选择/拖拽/缩放/旋转

FUXA 将这些操作**完全委托给 SVG-Edit**：

```typescript
// 选择 → 通过 SVG-Edit 回调 onSelected
private onSelectedElement(elems) {
    this.selectedElement = elems[0];
    this.selectedElement.type = elems[0].type || 'svg-ext-shapes-' + this.currentMode;
    this.checkColors(this.selectedElement);      // 同步颜色面板
    this.checkGaugeInView(this.selectedElement);  // 同步属性面板
    this.checkSvgElementsMap(false);              // 更新元素列表
}

// 对齐 → 代理到 SVG-Edit
onAlignSelected(letter: string) {
    this.winRef.nativeWindow.svgEditor.alignSelectedElements(letter.charAt(0));
}

// 移动步进
onMoveStepChange(step: number) {
    this.winRef.nativeWindow.svgEditor.setMoveStep(step);
}

// 颜色设置
private setFillColor(event) {
    this.winRef.nativeWindow.svgEditor.setColor(color, alfa, 'fill');
}
setStrokeColor(event) {
    this.winRef.nativeWindow.svgEditor.setColor(color, alfa, 'stroke');
}
```

### 2.4 Widget 工具箱（添加图元到画布）

```typescript
// 设置编辑模式（select, line, text, rect, circle, ...以及自定义类型）
setMode(mode: string, clearSelection: boolean = true) {
    this.currentMode = mode;
    this.winRef.nativeWindow.svgEditor.clickToSetMode(mode);
}

// FUXA 自定义图元类型前缀为 'svg-ext-'
// 例如: 'svg-ext-value-xx', 'svg-ext-button-xx', 'svg-ext-pipe-xx'
// SVG-Edit 扩展机制识别 'svg-ext-' 前缀，将其作为自定义控件处理
```

**添加图元的核心流程**：
1. 用户点击工具箱 → `setMode('own_ctrl-image')` 等
2. SVG-Edit 创建 SVG DOM 元素，自动分配 `id` (如 `svg_xxxxx`)
3. 设置元素的 `type` 属性为图元类型 (如 `svg-ext-button-xx`)
4. 触发 `onElementAdded` 回调
5. Editor 调用 `getGaugeSettings(eleadded)` 获取/创建 GaugeSettings
6. 调用 `checkGaugeAdded(ga)` 初始化图元（创建 Angular 组件等）
7. 调用 `setGaugeSettings(ga)` 将 GaugeSettings 写入 `currentView.items`

### 2.5 属性面板绑定

```typescript
// 当选中元素时，从 currentView.items 获取 GaugeSettings
getGaugeSettings(ele, initParams = null): GaugeSettings {
    if (ele && this.currentView) {
        if (this.currentView.items[ele.id]) {
            return this.currentView.items[ele.id];  // 已有配置
        }
        // 不存在则创建新的
        let gs = this.gaugesManager.createSettings(ele.id, ele.type);
        return gs;
    }
    return null;
}

// 打开属性编辑对话框
openEditGauge(settings, callback) {
    let dlgType = GaugesManager.getEditDialogTypeToUse(settings.type);
    // 根据类型选择不同的对话框组件
    // Chart → 侧边面板, Gauge → MatDialog, Pipe → 侧边面板...
}
```

### 2.6 保存/加载机制

```typescript
// 保存：提取 SVG 字符串 + items 字典一起存储
private getContent() {
    // SVG视图：从 SVG-Edit 获取完整SVG字符串
    return this.winRef.nativeWindow.svgEditor.getSvgString();
    // Cards视图：从 CardsView 组件获取
    // Maps视图：直接用 currentView.svgcontent
}

onSaveProject(notify = false) {
    this.currentView.svgcontent = this.getContent();
    this.saveView(this.currentView, notify);
    // → projectService.setView(view) → HTTP PUT to server
}

// 加载：将 SVG 字符串注入 SVG-Edit
private loadView(view: View) {
    this.clearEditor();  // svgEditor.clickClearAll()
    // 设置画面属性
    this.winRef.nativeWindow.svgEditor.setDocProperty(
        view.name, view.profile.width, view.profile.height, view.profile.bkcolor);
    // 注入 SVG 内容
    this.winRef.nativeWindow.svgEditor.setSvgString(svgcontent);
    // 延迟初始化所有图元
    setTimeout(() => {
        for (let key in v.items) {
            let ga = this.getGaugeSettings(v.items[key]);
            this.checkGaugeAdded(ga);
        }
    }, 500);
}
```

### 2.7 SVG 元素识别策略

```typescript
// FUXA 通过 SVG 元素的属性来识别图元：
// 1. id属性：图元唯一标识（如 'svg_xxxxx'）
// 2. type属性：图元类型标识（如 'svg-ext-value-xx'）

// 扫描所有 SVG 元素
checkSvgElementsMap(loadSvgElement = false) {
    this.svgElements = Array.from(
        document.querySelectorAll('g, text, line, rect, image, path, circle, ellipse')
    ).filter((svg: any) =>
        svg.attributes?.type?.value?.startsWith('svg-ext') ||
        (svg.id?.startsWith('svg_') && !svg.parentNode?.attributes?.type?.value?.startsWith('svg-ext'))
    ).map(ele => <ISvgElement>{id: ele.id, name: this.currentView.items[ele.id]?.name});
}
```

### 2.8 复制粘贴处理

```typescript
private onCopyAndPaste(copiedPasted: CopiedAndPasted) {
    // 1. 获取复制和粘贴的元素ID/Type树
    const copiedIdsAndTypes = Utils.getInTreeIdAndType(copied[i]);
    const pastedIdsAndTypes = Utils.getInTreeIdAndType(pasted[i]);

    // 2. 为每个粘贴元素创建新的 GaugeSettings
    let gaDest = this.gaugesManager.createSettings(pastedIdsAndTypes[j].id, pastedIdsAndTypes[j].type);
    gaDest.name = Utils.getNextName(prefix, names);  // 自动编号命名
    gaDest.property = JSON.parse(JSON.stringify(gaSrc.property));  // 深拷贝属性
    this.setGaugeSettings(gaDest);
    this.checkGaugeAdded(gaDest);
}
```

---

## 三、运行时渲染 (fuxa-view.component.ts)

### 3.1 运行时架构总览

```
┌─────────────────────────────────────────────┐
│              FuxaViewComponent               │
│                                              │
│  ┌──────────┐   innerHTML    ┌────────────┐ │
│  │ SVG内容  │ ─────────────→ │ DOM渲染    │ │
│  │ (字符串) │   SVG.adopt    │ (SVG元素)  │ │
│  └──────────┘                └─────┬──────┘ │
│                                     │        │
│  ┌──────────┐   processValue  ┌─────▼──────┐ │
│  │ 信号推送  │ ─────────────→ │ 属性更新    │ │
│  │ (WebSocket)│               │ (fill/text/ │ │
│  └──────────┘                 │  rotate...) │ │
│                               └────────────┘ │
│  ┌──────────┐                                │
│  │事件处理   │  click → runEvents → 页面/对话 │
│  └──────────┘               框/脚本/值设置    │
└─────────────────────────────────────────────┘
```

### 3.2 SVG 内容加载流程

```typescript
private loadResolvedHmi(view: View, legacyProfile?: boolean) {
    // 1. 清理旧内容
    this.gaugesManager.unbindGauge(this.id);
    this.clearGaugeStatus();
    this.viewContainerRef.clear();
    this.dataContainer.nativeElement.innerHTML = '';  // 🔑 清空DOM

    // 2. 注入 SVG 字符串到 DOM
    this.dataContainer.nativeElement.innerHTML = view.svgcontent.replace('<title>Layer 1</title>', '');

    // 3. 设置背景色和对齐
    if (view.profile?.bkcolor) {
        this.dataContainer.nativeElement.style.backgroundColor = view.profile.bkcolor;
    }

    // 4. 触发变更检测
    this.changeDetector.detectChanges();

    // 5. 绑定信号和事件
    this.loadWatch(this.view);

    // 6. 执行画面级 onOpen 事件
    view.property?.events?.forEach(event => {
        if (event.type === ViewEventType.onopen) {
            this.onRunScript(event);
        }
    });
}
```

### 3.3 信号绑定流程 (loadWatch)

```typescript
private loadWatch(view: View) {
    for (let key in view.items) {
        let gaugeSetting = items[key];

        // 1. 初始化图元组件
        let gauge = this.gaugesManager.initElementAdded(
            items[key], this.resolver, this.viewContainerRef, true, this, textTranslated, sourceTags);

        // 2. 绑定鼠标事件
        this.gaugesManager.bindGauge(gauge, this.id, items[key], sourceTags,
            (ga) => { this.onBindMouseEvents(ga); },   // 鼠标事件回调
            (ga) => { this.onBindHtmlEvent(ga); }       // HTML事件回调
        );

        // 3. 处理初始值
        if (gaugeSetting.property.variableId) {
            let variable = { id: gaugeSetting.property.variableId, value: gaugeSetting.property.variableValue };
            variables = [variable];
        }

        // 4. 获取最新信号值
        variables = variables.concat(this.gaugesManager.getBindSignalsValue(items[key]));

        // 5. 对每个 SVG 元素执行 processValue
        let svgeles = FuxaViewComponent.getSvgElements(gaugeSetting.id);
        for (let y = 0; y < svgeles.length; y++) {
            variables.forEach(variable => {
                this.gaugesManager.processValue(gaugeSetting, svgeles[y], variable, gaugeStatus);
            });
        }

        // 6. 执行 onLoad 事件
        const loadEvents = gaugeSetting.property.events?.filter(ev => ev.type === GaugeEventType.onLoad);
        if (loadEvents?.length) {
            this.runEvents(this, gaugeSetting, null, loadEvents);
        }
    }

    // 7. 订阅信号变更
    this.subscriptionOnChange = this.gaugesManager.onchange.subscribe(this.handleSignal.bind(this));

    // 8. 订阅服务端信号
    this.hmiService.viewsTagsSubscribe(this.gaugesManager.getBindedSignalsId(), true);
}
```

### 3.4 handleSignal 信号处理核心

```typescript
protected handleSignal(sig) {
    if (sig.value !== undefined) {
        // 1. 获取该信号绑定的所有图元设置
        let gas = this.gaugesManager.getGaugeSettings(this.id, sig.id);
        if (gas) {
            for (let i = 0; i < gas.length; i++) {
                let gaugeSetting = gas[i];
                let gaugeStatus = this.getGaugeStatus(gaugeSetting);

                // 2. 检查值是否变化（去重）
                if (this.checkStatusValue(gaugeSetting.id, gaugeStatus, sig)) {
                    // 3. 获取 DOM 中的 SVG 元素
                    let svgeles = FuxaViewComponent.getSvgElements(gaugeSetting.id);

                    // 4. 对每个 SVG 元素执行值处理
                    for (let y = 0; y < svgeles.length; y++) {
                        this.gaugesManager.processValue(gaugeSetting, svgeles[y], sig, gaugeStatus);
                    }
                }
            }
        }
    }
}
```

### 3.5 SVG 元素查找机制

```typescript
// 使用 SVG.js 的 adopt 方法将 DOM 元素转为 SVG.js 对象
private static getSvgElements(svgid: string) {
    let ele = document.getElementsByTagName('svg');
    let result = [];
    for (let i = 0; i < ele.length; i++) {
        let svgItems = ele[i].getElementById(svgid);
        if (svgItems) {
            result.push(SVG.adopt(svgItems));  // 🔑 SVG.adopt 包装 DOM → SVG.js 对象
        }
    }
    return result;
}
```

### 3.6 GaugesManager.processValue 分发逻辑

```typescript
processValue(ga: GaugeSettings, svgele: any, sig: Variable, gaugeStatus: GaugeStatus) {
    gaugeStatus.variablesValue[sig.id] = sig.value;

    // 根据图元类型分发到对应的静态处理方法
    for (let i = 0; i < GaugesManager.Gauges.length; i++) {
        if (ga.type.startsWith(GaugesManager.Gauges[i].TypeTag)) {
            if (ga.type.startsWith(HtmlChartComponent.TypeTag)) {
                // Chart 实时更新...
            } else if (ga.type.startsWith(HtmlBagComponent.TypeTag)) {
                // Gauge 仪表盘更新...
            } else if (typeof GaugesManager.Gauges[i]['processValue'] === 'function') {
                // 🔑 核心分发：调用对应图元类的静态 processValue 方法
                GaugesManager.Gauges[i]['processValue'](ga, svgele, sig, gaugeStatus);
                break;
            }
        }
    }
}
```

### 3.7 不同图元类型的数据响应方式

基于 GaugeActionsType 枚举和各图元 processValue 实现：

| 图元类型 | 数据变化响应 | 实现方式 |
|---------|-------------|---------|
| **Value** (文本输出) | 更新 textContent | `svgele.node.textContent = formattedValue` |
| **Button** | 更新文本/图标 | `HtmlButtonComponent.processValue()` |
| **Progress** (进度条) | 更新进度宽度 | `GaugeProgressComponent.processValue()` |
| **Semaphore** (信号灯) | 更新颜色 | `GaugeSemaphoreComponent.processValue()` |
| **Pipe** (管道) | 流动动画 | `PipeComponent.processValue()` |
| **Slider** | 更新滑块位置 | `SliderComponent.processValue()` |
| **Switch** | 更新开关状态 | `HtmlSwitchComponent.processValue()` |
| **Chart** | 实时数据点 | `HtmlChartComponent.processValue()` |
| **Table** | 实时行数据 | `HtmlTableComponent.processValue()` |
| **Shapes** (SVG形状) | **Actions驱动** | 通过 ranges/actions 配置 |

### 3.8 Shapes 组件的 processValue（最关键的通用图元处理）

Shapes 是最核心的图元类型，所有基本 SVG 元素（path, rect, circle, line, text, image 等）都通过它处理数据绑定：

```typescript
// ShapesComponent.processValue 核心逻辑（伪代码重构）：
static processValue(ga: GaugeSettings, svgele, sig: Variable, gaugeStatus: GaugeStatus) {
    let value = GaugeBaseComponent.checkBitmask(ga.property.bitmask, Number(sig.value));
    let pro = ga.property;

    // 1. 处理 ranges（值域颜色/文本映射）
    if (pro.ranges) {
        for (let i = 0; i < pro.ranges.length; i++) {
            let range = pro.ranges[i];
            if (value >= range.min && value <= range.max) {
                // 设置填充色
                if (range.color) svgele.attr('fill', range.color);
                // 设置描边色
                if (range.stroke) svgele.attr('stroke', range.stroke);
                // 设置文本
                if (range.text) {
                    let textNode = svgele.node.querySelector('text') || svgele;
                    textNode.textContent = range.text;
                }
                break;
            }
        }
    }

    // 2. 处理 actions（数据驱动动画）
    if (pro.actions) {
        pro.actions.forEach(act => {
            let actValue = GaugeBaseComponent.checkBitmask(act.bitmask, Number(sig.value));
            let inRange = (actValue >= act.range.min && actValue <= act.range.max);

            switch (act.type) {
                case 'hide':
                    inRange ? GaugeBaseComponent.runActionHide(svgele, act.type, gaugeStatus)
                            : GaugeBaseComponent.runActionShow(svgele, act.type, gaugeStatus);
                    break;
                case 'show':
                    inRange ? GaugeBaseComponent.runActionShow(svgele, act.type, gaugeStatus)
                            : GaugeBaseComponent.runActionHide(svgele, act.type, gaugeStatus);
                    break;
                case 'blink':
                    GaugeBaseComponent.checkActionBlink(svgele, act, gaugeStatus, inRange, false);
                    break;
                case 'color':
                    if (inRange) {
                        if (act.options.fill) svgele.attr('fill', act.options.fill);
                        if (act.options.stroke) svgele.attr('stroke', act.options.stroke);
                    }
                    break;
                case 'rotate':
                    // 线性插值角度
                    let angle = minAngle + (actValue - act.range.min) / (act.range.max - act.range.min) * (maxAngle - minAngle);
                    svgele.rotate(angle);
                    break;
                case 'move':
                    // 平移动画
                    svgele.animate().move(act.options.toX, act.options.toY);
                    break;
                case 'moveByTags':
                    // 按Tag值比例移动
                    break;
                case 'downup':
                    // 上下动画
                    break;
                case 'clockwise':
                    // 顺时针旋转动画
                    break;
                case 'anticlockwise':
                    // 逆时针旋转动画
                    break;
            }
        });
    }
}
```

### 3.9 事件系统

```typescript
// 鼠标事件绑定
private onBindMouseEvents(ga: GaugeSettings) {
    let svgele = FuxaViewComponent.getSvgElement(ga.id);
    let clickEvents = self.gaugesManager.getBindMouseEvent(ga, GaugeEventType.click);
    let dblclickEvents = self.gaugesManager.getBindMouseEvent(ga, GaugeEventType.dblclick);

    // 单击（带双击延迟判断）
    svgele.click(function(ev) {
        clearTimeout(clickTimeout);
        clickTimeout = setTimeout(function() {
            self.runEvents(self, ga, ev, clickEvents);
        }, dblclickEvents?.length > 0 ? 200 : 0);
    });

    // 其他鼠标事件：mousedown, mouseup, mouseover, mouseout
}

// 事件分发执行
public runEvents(self, ga, ev, events) {
    for (let i = 0; i < events.length; i++) {
        switch (events[i].action) {
            case 'onpage':     → loadPage(viewref)
            case 'onwindow':   → onOpenCard(viewref)     // 浮动窗口
            case 'ondialog':   → openDialog(viewref)     // 对话框
            case 'oniframe':   → openIframe(url)         // 内嵌框架
            case 'onSetValue': → onSetValue(value)       // 设置值
            case 'onToggleValue': → onToggleValue()      // 切换值
            case 'onSetInput': → onSetInput()            // 从输入获取值
            case 'onclose':    → onClose()                // 关闭
            case 'onRunScript': → onRunScript(scriptId)  // 运行脚本
            case 'onViewToPanel': → onSetViewToPanel()    // 面板切换
            case 'onMonitor':  → onMonitor(viewref)       // 监控
        }
    }
}
```

### 3.10 变量映射（模板机制）

```typescript
// FUXA 支持 Placeholder 变量映射，用于画面模板化
// Placeholder格式: @tagName@
// 例如: input控件的variableId可以是 "@Temperature@"
// 当画面作为子面板加载时，"@Temperature@" 映射到实际Tag ID

protected applyVariableMappingTo(target, tags?: Tag[]) {
    if (this.plainVariableMapping.hasOwnProperty(target.variableId)) {
        target.variableValue = this.plainVariableMapping[target.variableId]?.variableValue;
        target.variableId = this.plainVariableMapping[target.variableId]?.variableId;
    }
    // 也支持通过设备Tag名称自动映射
    if (tags) {
        const tag = DevicesUtils.placeholderToTag(target.variableId, tags);
        if (tag) {
            target.variableId = tag.id;
            target.variableValue = tag.value;
        }
    }
}
```

---

## 四、GaugesManager 图元引擎

### 4.1 已注册图元列表

```typescript
static Gauges = [
    ValueComponent,          // 文本输出  → 'svg-ext-value'
    HtmlInputComponent,      // 输入框   → 'svg-ext-input'
    HtmlButtonComponent,     // 按钮     → 'svg-ext-button'
    HtmlBagComponent,        // 仪表盘   → 'svg-ext-gauge'
    HtmlSelectComponent,     // 下拉选择 → 'svg-ext-select'
    HtmlChartComponent,      // 趋势图   → 'svg-ext-chart'
    GaugeProgressComponent,  // 进度条   → 'svg-ext-progress'
    GaugeSemaphoreComponent, // 信号灯   → 'svg-ext-led'
    ShapesComponent,         // 通用形状 → 'svg-ext-shapes'
    ProcEngComponent,        // 工程形状 → 'svg-ext-proceng'
    ApeShapesComponent,      // APE形状  → 'svg-ext-apeshapes'
    PipeComponent,           // 管道     → 'svg-ext-pipe'
    SliderComponent,         // 滑块     → 'svg-ext-slider'
    HtmlSwitchComponent,     // 开关     → 'svg-ext-switch'
    HtmlGraphComponent,      // 图表     → 'svg-ext-graph'
    HtmlIframeComponent,     // 内嵌框架 → 'svg-ext-iframe'
    HtmlTableComponent,      // 数据表格 → 'svg-ext-table'
    HtmlImageComponent,      // 图片     → 'svg-ext-image'
    PanelComponent,          // 面板     → 'svg-ext-panel'
    HtmlVideoComponent,      // 视频     → 'svg-ext-video'
    HtmlSchedulerComponent,  // 调度器   → 'svg-ext-scheduler'
];
```

### 4.2 关键方法签名

```typescript
// 创建图元配置
createSettings(id: string, type: string): GaugeSettings

// 初始化图元DOM组件
initElementAdded(ga: GaugeSettings, res: any, ref: any, isview: boolean,
                 parent?: FuxaViewComponent, textTranslation?: string,
                 sourceDeviceTags?: Tag[]): any

// 绑定图元到信号和事件
bindGauge(gauge: any, domViewId: string, ga: GaugeSettings,
          sourceDeviceTags: Tag[],
          bindMouseEvent: (ga) => void,
          bindhtmlevent: (event) => void): void

// 处理信号值 → 分发到图元
processValue(ga: GaugeSettings, svgele: any, sig: Variable, gaugeStatus: GaugeStatus): void

// 获取绑定的信号ID列表
getBindSignals(gaugeSettings: GaugeSettings, sourceDeviceTags?: Tag[]): string[]

// 获取绑定的鼠标事件
getBindMouseEvent(ga: GaugeSettings, evType: GaugeEventType): GaugeEvent[]

// 发送信号值到后端
putSignalValue(sigid: string, val: string, fnc?: string): void
```

### 4.3 信号-Gauge 映射机制

```
memorySigGauges = {
    [signalId]: {
        [gaugeId]: gaugeComponent  // Chart/Graph/Table等需要引用组件实例的图元
    }
}

// HmiService 维护:
// signalGaugeMap = {
//     [domViewId]: {
//         [signalId]: GaugeSettings[]
//     }
// }
```

---

## 五、Device/Tag 模型 (device.ts)

### 5.1 核心类

```typescript
class Device {
    id: string;              // GUID
    name: string;            // 设备名称
    enabled: boolean;        // 是否启用
    property: DeviceNetProperty;  // 连接属性（IP/端口/从站ID等）
    type: DeviceType;        // 设备类型
    polling: number;         // 轮询间隔(ms)
    tags: DictionaryTag;     // Tag字典
}

class Tag {
    id: string;              // GUID
    name: string;            // Tag名称
    type: string;            // 数据类型
    address: string;         // 地址
    memaddress: string;      // Modbus内存地址
    divisor: number;         // 值除数
    format: number;          // 小数位数
    daq: TagDaq;            // DAQ采集配置
    scale: TagScale;         // 值缩放
    options: any;            // MQTT等扩展选项
}

// DeviceType 支持的协议
enum DeviceType {
    FuxaServer, SiemensS7, OPCUA, BACnet,
    ModbusRTU, ModbusTCP, WebAPI, MQTTclient,
    internal, EthernetIP, OmronEthernetIP,
    ODBC, ADSclient, GPIO, WebCam, MELSEC, REDIS
}
```

---

## 六、架构设计模式总结

### 6.1 存储架构：SVG字符串 + 元数据字典

```
View {
    svgcontent: "<svg>...</svg>"     // 完整SVG代码（包含所有图元的DOM结构）
    items: {                          // 与SVG元素id对应的元数据字典
        "svg_abc123": GaugeSettings {  // id = SVG元素id
            name: "button_1",
            type: "svg-ext-button-xx",
            property: GaugeProperty {
                variableId: "t_xxx",
                ranges: [...],
                events: [...],
                actions: [...]
            }
        },
        "svg_def456": GaugeSettings { ... }
    }
}
```

**核心思路**：SVG DOM 自身就是图元的"画布"，SVG元素通过 `id` 和 `type` 属性与 items 字典中的 GaugeSettings 关联。这是**关注点分离**的经典设计：
- SVG字符串负责**视觉表现**（位置、大小、颜色、形状）
- items字典负责**数据绑定**（信号映射、事件、动画）

### 6.2 编辑器-运行时分离

```
编辑模式 (EditorComponent):
  SVG-Edit → 操作SVG DOM → 保存为svgcontent字符串 + items字典
  GaugesManager.initElementAdded(ga, res, ref, false)  // isview=false

运行模式 (FuxaViewComponent):
  innerHTML(svgcontent) → SVG.adopt → 绑定信号 → processValue
  GaugesManager.initElementAdded(ga, res, ref, true)   // isview=true
```

### 6.3 信号传播链

```
后端WebSocket → HmiService.onVariableChanged
  → GaugesManager.onchange.emit(sig)
    → FuxaViewComponent.handleSignal(sig)
      → GaugesManager.getGaugeSettings(viewId, sigId)
        → 对每个匹配的 GaugeSettings:
          → FuxaViewComponent.getSvgElements(ga.id)
            → GaugesManager.processValue(ga, svgele, sig, gaugeStatus)
              → [Component].processValue(ga, svgele, sig, gaugeStatus)
                → svgele.attr('fill', color) / svgele.node.textContent = text / ...
```

### 6.4 图元注册机制

每个图元组件类定义静态属性和方法：
- `TypeTag: string` — SVG type 属性前缀
- `LabelTag: string` — UI显示标签
- `processValue(ga, svgele, sig, gaugeStatus)` — 数据更新处理
- `initElement(ga, ...)` — DOM初始化
- `getEvents(property, eventType)` — 事件获取
- `getSignals(property)` — 信号绑定
- `getDialogType()` — 属性对话框类型

---

## 七、重写指导建议

### 7.1 不依赖 SVG-Edit 的替代方案

FUXA 依赖 SVG-Edit（全局JS变量+回调）的方式非常脆弱。替代方案：

1. **SVG.js + 自研编辑器**：保留 SVG.js 用于运行时 DOM 操作，编辑器自研
2. **Canvas 混合**：编辑用 Canvas/Fabric，运行时转为 SVG
3. **纯 SVG.js**：编辑和运行时都用 SVG.js（当前项目的选择）

### 7.2 必须保留的核心设计

1. **SVG字符串 + items字典** 的双层存储
2. **GaugeSettings 作为元数据中枢**
3. **ranges + actions** 的数据驱动模型
4. **GaugeBaseComponent 的公共方法集**（blink/rotate/move/hide/show）
5. **信号-Gauge映射**的快速查找结构
6. **Placeholder 变量映射**机制（画面模板化）

### 7.3 可以优化的方面

1. 用 TypeScript 严格类型替代 `declare var` + 全局变量
2. 用 RxJS/Proxy 替代 setInterval 的 blink 实现
3. 用 CSS transform 替代 SVG attribute 操作实现动画
4. 将图元注册从静态数组改为依赖注入/插件机制
5. 添加虚拟 DOM diff 减少不必要的 DOM 操作
