# FUXA SCADA 编辑器核心源码深度分析报告

> 源码版本: FUXA master 分支 (2026-08)
> 文件根路径: `client/src/app/`

---

## 一、editor.component.ts — 编辑器主组件 (65891 bytes)

### 1. 整体架构

FUXA 编辑器**不是自己实现 SVG 画布**，而是封装了一个**基于 SVG-Edit (svg-editor) 的 JavaScript 库**作为底层画布引擎。编辑器组件是 Angular 组件，但核心交互逻辑委托给全局变量暴露的 JS 库：

```typescript
declare var mypathseg: any;       // SVG Path 段初始化
declare var mybrowser: any;       // 浏览器兼容检测
declare var mysvgutils: any;      // SVG 工具集
declare var myselect: any;        // 选择逻辑
declare var mydraw: any;          // 绘制逻辑
declare var mysvgcanvas: any;     // SVG 画布核心
declare var mysvgeditor: any;     // SVG 编辑器总入口
declare var $: any;               // jQuery (用于上下文菜单)
```

**关键发现**: FUXA 的画布交互（选择、拖拽、缩放、撤销重做等）全部在 `svgcanvas.js` / `svgeditor.js` 这些原生 JS 库中实现，Angular 组件只是一个胶水层。

### 2. 初始化链路 (myInit)

```typescript
private myInit() {
    mypathseg.initPathSeg();
    mybrowser.initBrowser();
    mysvgutils.initSvgutils();
    myselect.initSelect();
    mydraw.initDraw();
    mysvgcanvas.initSvgCanvas();
    
    // 核心: 初始化 svg-editor，传入6个回调
    let toinit = mysvgeditor.initSvgEditor($,
        (selected) => { /* 选中回调 */ },
        (type, args) => { /* 扩展加载回调 */ },
        (type, color) => { /* 颜色变更回调 */ },
        (eleadded) => { /* 元素添加回调 */ },
        (eleremoved) => { /* 元素删除回调 */ },
        (eleresized) => { /* 元素缩放回调 */ },
        (copiedPasted) => { /* 复制粘贴回调 */ },
        () => { /* 分组变更回调 */ }
    );
    
    this.winRef.nativeWindow.svgEditor.init();
    this.winRef.nativeWindow.svgEditor.setMoveStep(this.moveStep);
    $(initContextmenu);  // 初始化右键菜单
}
```

### 3. 鼠标事件处理链路

**全部委托给 svgEditor/svgcanvas**，Angular 组件不直接处理 mousedown/mousemove/mouseup。

- `mysvgcanvas.initSvgCanvas()` → 内部注册所有鼠标事件
- `myselect.initSelect()` → 选择逻辑（rubber-band、选择框）
- `mydraw.initDraw()` → 绘制逻辑

**Angular 组件通过回调接收结果**：
- 选中回调 → `onSelectedElement(elems)`
- 元素添加回调 → `getGaugeSettings()` + `checkGaugeAdded()`
- 元素缩放回调 → `gaugesManager.checkElementToResize()`

### 4. 图元选中实现

```typescript
private onSelectedElement(elems) {
    this.selectedElement = null;
    if (document.activeElement !== document.body) {
        (document.activeElement as HTMLElement).blur();
    }
    if (elems) {
        if (elems.length <= 1) {
            this.selectedElement = elems[0];
            this.selectedElement.type = elems[0].type || 'svg-ext-shapes-' + (this.currentMode || 'default');
            this.checkColors(this.selectedElement);
            this.checkGaugeInView(this.selectedElement);
        }
    }
    this.checkSvgElementsMap(false);
}
```

**选中元素识别**: 通过 `svgEditor.getSelectedElements()` 获取选中数组
**多选**: 由底层 svgcanvas 处理 rubber-band 选择
**高亮**: SVG-Edit 内部在选择元素上绘制选择框 + resize handles

### 5. 拖拽移动 & 吸附网格

```typescript
// 移动步长（吸附网格大小）
moveStep = 1;
readonly moveStepOptions = [1, 2, 3, 5, 10];

onMoveStepChange(step: number | string) {
    this.moveStep = parsedStep;
    this.winRef.nativeWindow.svgEditor.setMoveStep(parsedStep);
}

// 网格显示 & 吸附
onShowGrid() {
    this.gridOn = !this.gridOn;
    this.winRef.nativeWindow.svgEditor.clickExtension('view_grid');
    this.winRef.nativeWindow.svgEditor.enableGridSnapping(this.gridOn);
}
```

**关键**: 移动步长和网格吸附全部由 `svgEditor.setMoveStep()` 和 `svgEditor.enableGridSnapping()` 实现。

### 6. 模式切换（绘图工具）

```typescript
setMode(mode: string, clearSelection: boolean = true) {
    this.currentMode = mode;
    if (clearSelection) {
        this.clearSelection();
        this.checkFillAndStrokeColor();
    }
    this.winRef.nativeWindow.svgEditor.clickToSetMode(mode);
}
```

**支持的模式**:
- 基本图形: `select`, `fhpath`(铅笔), `line`, `rect`, `circle`, `ellipse`, `path`, `text`, `image`
- 控件: `html_input`, `value`, `html_button`, `html_select`, `gauge_progress`, `gauge_semaphore`, `html_chart`, `html_bag`, `pipe`, `html_slider`, `html_switch`, `html_graph-bar`, `own_ctrl-table`, `own_ctrl-iframe`, `html_graph-pie`, `own_ctrl-image`, `own_ctrl-panel`, `own_ctrl-video`, `own_ctrl-scheduler`
- SVG Shapes: 动态加载的 SVG 形状库

### 7. 缩放句柄 (Resize Handle)

**由 SVG-Edit 底层实现**，FUXA 不直接管理。通过 `eleresized` 回调接收：

```typescript
(eleresized) => {
    if (eleresized && eleresized.id) {
        let ga = this.getGaugeSettings(eleresized);
        this.gaugesManager.checkElementToResize(ga, this.resolver, this.viewContainerRef, eleresized.size);
    }
}
```

### 8. 对齐操作

```typescript
onAlignSelected(letter: string) {
    this.winRef.nativeWindow.svgEditor.alignSelectedElements(letter.charAt(0));
}
```

6种对齐: left, center, right, top, middle, bottom — 全部委托 `svgEditor.alignSelectedElements()`

### 9. 撤销/重做

**由 SVG-Edit 底层 undo stack 实现**:

```typescript
// 加载 view 后重置 undo stack
this.winRef.nativeWindow.svgEditor.resetUndoStack();
```

### 10. 组合/取消组合

通过 `onGroupChanged` 回调:

```typescript
() => { // onGroupChanged
    this.checkSvgElementsMap(true);
}
```

底层 svgEditor 处理 group 操作，变更后通知 Angular 更新元素映射。

### 11. 右键菜单

```typescript
$(initContextmenu);  // jQuery 初始化上下文菜单
```

### 12. GaugeSettings 管理（数据绑定核心）

每个 SVG 元素对应一个 `GaugeSettings`，存储在 `view.items` 字典中:

```typescript
getGaugeSettings(ele, initParams = null): GaugeSettings {
    if (ele && this.currentView) {
        if (this.currentView.items[ele.id]) {
            return this.currentView.items[ele.id];
        }
        // 新建空 settings
        let gs = this.gaugesManager.createSettings(ele.id, ele.type);
        if (initParams) {
            gs.property = new GaugeProperty();
            gs.property.address = initParams;
        }
        return gs;
    }
    return null;
}
```

### 13. 编辑器三种模式

```typescript
enum EditorModeType {
    SVG,    // SVG 画布编辑
    CARDS,  // 卡片视图编辑
    MAPS    // 地图视图编辑
}
```

### 14. 颜色系统

```typescript
readonly colorDefault = { fill: '#FFFFFF', stroke: '#000000' };

onChangeFillColor(event) → setFillColor() → svgEditor.setColor(color, alfa, 'fill')
onChangeStrokeColor(event) → setStrokeColor() → svgEditor.setColor(color, alfa, 'stroke')
```

### 15. 序列化 (保存)

```typescript
private getContent() {
    if (this.currentView.type === ViewType.cards) {
        this.currentView.svgcontent = this.cardsview.getContent();
        return this.currentView.svgcontent;
    } else if (this.currentView.type === ViewType.maps) {
        return this.currentView.svgcontent;
    }
    // SVG 视图: 从 svgEditor 导出 SVG 字符串
    return this.winRef.nativeWindow.svgEditor.getSvgString();
}
```

---

## 二、editor.component.html — 编辑器模板 (82460 bytes)

### 左侧栏结构 (4个可折叠面板)

1. **Views 面板** — 视图列表，支持添加/导入/删除/克隆/重命名
2. **General 面板** — 基本绘图工具（选择/铅笔/直线/矩形/圆形/椭圆/路径/文字/图片）
3. **Controls 面板** — 19种控件工具:
   - 输入框(html_input), 输出(value), 按钮(html_button), 下拉选择(html_select)
   - 进度条(gauge_progress), 信号灯(gauge_semaphore), 图表(html_chart)
   - 仪表盘(html_bag), 管道(pipe), 滑块(html_slider), 开关(html_switch)
   - 柱状图(html_graph-bar), 表格(own_ctrl-table), iframe(own_ctrl-iframe)
   - 饼图(html_graph-pie), 图片控件(own_ctrl-image), 面板(own_ctrl-panel)
   - 视频(own_ctrl-video), 调度器(own_ctrl-scheduler)
4. **Shapes 面板** — 动态加载的 SVG 形状库（可多组）
5. **Widgets 面板** — 社区 Widget 库
6. **Resources 面板** — 资源管理

### 右侧浮窗结构（选中元素后显示）

1. **Interactivity** — ID / Class 编辑
2. **Transform** — 位置(x,y) / 尺寸(width,height) / 圆角(radius) / 角度(angle) / 隐藏(hide) / 锁定(lock)
   - 按元素类型动态显示: rect_panel, circle_panel, ellipse_panel, text_panel, image_panel, htmlctrl_panel, shape_panel
3. **Align** — 6种对齐按钮（左/中/右/上/中/下）
4. **Stroke** — 线宽 / 虚线样式 / 线连接(join) / 线端(cap) / 阴影
5. **Marker** — 箭头标记（开始/中间/结束）
6. **Hyperlink** — 链接设置

### 底部栏
- 填充色选择器
- 描边色选择器

---

## 三、fuxa-view.component.ts — 画面渲染组件

### 1. SVG 渲染方式: **innerHTML + SVG.js**

```typescript
// 直接设置 innerHTML 加载 SVG 内容
this.dataContainer.nativeElement.innerHTML = view.svgcontent.replace('<title>Layer 1</title>', '');
```

**然后使用 SVG.js (通过 `SVG.adopt()`) 操作已渲染的 SVG DOM**:

```typescript
private static getSvgElements(svgid: string) {
    let ele = document.getElementsByTagName('svg');
    let result = [];
    for (let i = 0; i < ele.length; i++) {
        let svgItems = ele[i].getElementById(svgid);
        if (svgItems) {
            result.push(SVG.adopt(svgItems));  // SVG.js adopt 现有 DOM
        }
    }
    return result;
}
```

### 2. 运行时数据绑定逻辑 (loadWatch)

核心流程:

```
loadHmi() → loadResolvedHmi() → loadWatch()
```

`loadWatch()` 是数据绑定的核心:

```typescript
private loadWatch(view: View) {
    // 1. 应用变量映射（替换 placeholder）
    let items = this.applyVariableMapping(view.items, sourceTags);
    
    // 2. 遍历所有 items
    for (let key in items) {
        // 3. 初始化 gauge (动态创建 Angular 组件)
        let gauge = this.gaugesManager.initElementAdded(items[key], this.resolver, this.viewContainerRef, true, this, textTranslated, sourceTags);
        
        // 4. 绑定鼠标/键盘事件
        this.gaugesManager.bindGauge(gauge, this.id, items[key], sourceTags, bindMouseEvents, bindHtmlEvent);
        
        // 5. 处理初始值
        if (items[key].property.variableValue || gaugeSetting.property.variableId) {
            // 获取初始变量值
            variables = [variable];
        }
        // 获取绑定信号的最新值
        variables = variables.concat(this.gaugesManager.getBindSignalsValue(items[key]));
        
        // 6. 执行 processValue 处理初始数据
        for (let y = 0; y < svgeles.length; y++) {
            variables.forEach(variable => {
                this.gaugesManager.processValue(gaugeSetting, svgeles[y], variable, gaugeStatus);
            });
        }
        
        // 7. 执行 onLoad 事件
        if (gaugeSetting.property.events) {
            const loadEvents = gaugeSetting.property.events?.filter(ev => ev.type === 'onLoad');
            this.runEvents(this, gaugeSetting, null, loadEvents);
        }
    }
    
    // 8. 订阅信号变更
    this.subscriptionOnChange = this.gaugesManager.onchange.subscribe(this.handleSignal.bind(this));
    
    // 9. 订阅服务端信号
    this.hmiService.viewsTagsSubscribe(this.gaugesManager.getBindedSignalsId(), true);
}
```

### 3. processValue 调用链路

```
handleSignal(sig) 
  → gaugesManager.getGaugeSettings(this.id, sig.id)  // 获取绑定到此信号的 gauge
  → getGaugeStatus(gaugeSetting)                      // 获取/创建 gauge 状态
  → checkStatusValue()                                // 检查值是否变更
  → getSvgElements(gaugeSetting.id)                    // 获取 SVG DOM 元素
  → gaugesManager.processValue(gaugeSetting, svgele, sig, gaugeStatus)
      → 根据 gauge 类型分发:
          HtmlChartComponent.processValue()
          GaugeProgressComponent.processValue()
          ShapesComponent.processValue()
          PipeComponent.processValue()
          ...
```

### 4. 事件系统

**支持的事件类型** (GaugeEventType):
- `click`, `dblclick`, `mousedown`, `mouseup`, `mouseover`, `mouseout`
- `enter` (键盘回车), `select` (下拉选择), `onLoad`

**支持的动作类型** (GaugeEventActionType):
- `onpage` — 跳转到页面
- `onwindow` — 打开浮动窗口
- `ondialog` — 打开对话框
- `oniframe` — 打开 iframe
- `onSetValue` — 设置值
- `onToggleValue` — 切换值
- `onSetInput` — 从输入获取值设置
- `onclose` — 关闭
- `onRunScript` — 运行脚本
- `onViewToPanel` — 面板内切换视图
- `onMonitor` — 监控
- `onOpenTab` — 打开新标签

### 5. 特殊图元处理

FUXA 在 SVG 视图中嵌入了多种"HTML 控件"，这些不是纯 SVG 图元，而是通过 Angular 动态组件加载机制在 SVG 中的 `<foreignObject>` 内渲染:

```
HtmlInputComponent  → <input> 控件
HtmlButtonComponent → <button> 控件
HtmlSelectComponent → <select> 控件
HtmlChartComponent  → Chart (uplot) 图表
HtmlBagComponent    → 仪表盘 Gauge
PipeComponent       → SVG 管道动画
SliderComponent     → 滑块控件
HtmlSwitchComponent → 开关控件
PanelComponent      → 嵌套视图面板
HtmlTableComponent  → 数据表格
HtmlImageComponent  → 动态图片
HtmlVideoComponent  → 视频播放
HtmlSchedulerComponent → 调度器
```

---

## 四、hmi.ts — HMI 图元定义模型

### 1. 核心类结构

```
Hmi
├── layout: LayoutSettings          // 全局布局
│   ├── autoresize, start, showdev
│   ├── navigation: NavigationSettings (mode, type, bkcolor, fgcolor, items)
│   ├── header: HeaderSettings (title, alarms, infos, bkcolor, fgcolor, items)
│   ├── zoom, inputdialog, hidenavigation
│   ├── theme, loginonstart, customStyles
│   └── show_connection_error
└── views: View[]                   // 视图列表

View
├── id: string                      // 随机ID (v_xxxxx)
├── name: string                    // 视图名称
├── profile: DocProfile             // 画面尺寸
│   ├── width (默认1024), height (默认768)
│   ├── bkcolor, margin, align
│   ├── gridType (Fixed)
│   └── viewRenderDelay
├── items: DictionaryGaugeSettings  // 图元字典 {id: GaugeSettings}
├── variables: DictionaryVariables  // 变量字典
├── svgcontent: string              // SVG 字符串
├── type: ViewType                  // svg | cards | maps
└── property: ViewProperty          // 视图级属性
    └── events: GaugeEvent[]

GaugeSettings
├── id: string                      // SVG 元素 ID
├── type: string                    // 控件类型标签
├── name: string                    // 显示名称
├── property: GaugeProperty         // 数据绑定属性
├── label: string                   // 类型标签
├── hide: boolean                   // 是否隐藏
└── lock: boolean                   // 是否锁定

GaugeProperty (核心数据绑定结构)
├── variableId: string              // 绑定的变量ID (Tag ID)
├── variableValue: string           // 变量初始值
├── bitmask: number                 // 位掩码
├── permission: number              // 权限级别
├── permissionRoles: PermissionRoles // 角色权限 {show[], enabled[]}
├── ranges: GaugeRangeProperty[]    // 范围映射 (值→颜色/文字/样式)
│   ├── min, max, text, textId, color, type, style, stroke
├── events: GaugeEvent[]            // 事件列表
│   ├── type (click/dblclick/...)
│   ├── action (onpage/onwindow/...)
│   ├── actparam, actoptions
├── actions: GaugeAction[]           // 动作列表（动画）
│   ├── variableId, bitmask, range, type, options
├── options: any                     // 控件特有选项
├── readonly: boolean
├── text: string                     // 文字属性（按钮等）
├── icon: string                     // Material图标
└── image: string                    // 图片资源

WidgetProperty extends GaugeProperty
├── type: string                    // Widget 类型
├── scriptContent: {moduleId, content}
├── svgContent: string
└── varsToBind: WidgetPropertyVariable[]
```

### 2. 默认图元库类型

```
GaugesManager.Gauges = [
    ValueComponent,          // 输出显示
    HtmlInputComponent,      // 输入框
    HtmlButtonComponent,     // 按钮
    HtmlBagComponent,        // 仪表盘 Gauge
    HtmlSelectComponent,     // 下拉选择
    HtmlChartComponent,      // 实时图表
    GaugeProgressComponent,  // 进度条
    GaugeSemaphoreComponent, // 信号灯/LED
    ShapesComponent,         // SVG 形状 (通用)
    ProcEngComponent,        // 工程符号 (阀/泵/管)
    ApeShapesComponent,      // APE 图形库
    PipeComponent,           // 管道
    SliderComponent,         // 滑块
    HtmlSwitchComponent,     // 开关
    HtmlGraphComponent,      // DAQ 图表
    HtmlIframeComponent,     // iframe
    HtmlTableComponent,      // 数据表格
    HtmlImageComponent,      // 动态图片
    PanelComponent,          // 嵌套面板
    HtmlVideoComponent,      // 视频播放
    HtmlSchedulerComponent   // 调度器
]
```

### 3. 序列化/反序列化格式

**View 序列化为 JSON**:
```json
{
    "id": "v_abc123",
    "name": "View_1",
    "type": "svg",
    "profile": {"width": 1024, "height": 768, "bkcolor": "#ffffffff"},
    "svgcontent": "<svg>...</svg>",
    "items": {
        "svg_xxx1": {
            "id": "svg_xxx1",
            "type": "svg-ext-value-xxx",
            "name": "output_1",
            "property": {
                "variableId": "tag_123",
                "ranges": [...],
                "events": [...],
                "actions": [...]
            },
            "hide": false,
            "lock": false
        }
    },
    "variables": {},
    "property": {"events": []}
}
```

**SVG 内容中的图元标识**: 通过 SVG 元素的 `type` 属性标识:
- 纯 SVG 图元: 无 `type` 或 `type` 不以 `svg-ext-` 开头
- FUXA 控件: `type="svg-ext-value-xxx"`, `type="svg-ext-html_input-xxx"`, 等
- SVG 形状库: `type="svg-ext-shapes-xxx"`, `type="svg-ext-proc-eng-xxx"`

---

## 五、gauges.component.ts (GaugesManager) — 图元管理引擎

### 1. processValue 分发机制

```typescript
processValue(ga, svgele, sig, gaugeStatus) {
    for (let i = 0; i < GaugesManager.Gauges.length; i++) {
        if (ga.type.startsWith(GaugesManager.Gauges[i].TypeTag)) {
            // 按类型分发到对应组件的静态 processValue 方法
            GaugesManager.Gauges[i]['processValue'](ga, svgele, sig, gaugeStatus);
            break;
        }
    }
}
```

### 2. 信号绑定机制

```typescript
bindGauge(gauge, domViewId, ga, sourceDeviceTags, bindMouseEvent, bindHtmlEvent) {
    // 1. 获取 gauge 绑定的信号 ID 列表
    let sigsId = this.getBindSignals(ga, sourceDeviceTags);
    
    // 2. 将信号→gauge 映射写入 hmiService
    sigsId.forEach(sigId => {
        this.hmiService.addSignalGaugeToMap(domViewId, sigId, ga);
    });
    
    // 3. 绑定鼠标事件
    if (mouseEvents.length > 0) {
        this.eventGauge[ga.id] = ga;
        bindMouseEvent(ga);  // → FuxaViewComponent.onBindMouseEvents()
    }
    
    // 4. 绑定 HTML 事件
    if (htmlEvents) {
        bindhtmlevent(htmlEvents);  // → FuxaViewComponent.onBindHtmlEvent()
    }
}
```

### 3. 信号值写入

```typescript
putEvent(event) {
    // 位掩码处理
    const value = GaugeBaseComponent.valueBitmask(event.ga.property.bitmask, event.value, current);
    this.hmiService.putSignalValue(event.ga.property.variableId, String(value));
}

putSignalValue(sigid, val, fnc) {
    this.hmiService.putSignalValue(sigid, val, fnc);
}
```

---

## 六、gauge-property.component.ts — 属性编辑面板

### 1. 对话框类型 (GaugeDialogType)

```typescript
enum GaugeDialogType {
    Range,            // 范围映射
    RangeAndText,     // 范围+文字
    RangeWithAlarm,   // 范围+报警
    ValueAndUnit,     // 值+单位
    ValueWithRef,     // 引用值
    Step,             // 步进
    MinMax,           // 最小最大
    Chart,            // 图表
    Gauge,            // 仪表盘
    Pipe,             // 管道
    Slider,           // 滑块
    Switch,           // 开关
    Graph,            // DAQ图表
    Iframe,           // iframe
    Table,            // 表格
    Input,            // 输入框
    Panel,            // 面板
    Video,            // 视频
    Scheduler         // 调度器
}
```

### 2. 属性面板结构

```typescript
class GaugePropertyComponent {
    @ViewChild('flexhead') flexHead: FlexHeadComponent;      // 属性头部（值/范围/单位）
    @ViewChild('flexevent') flexEvent: FlexEventComponent;   // 事件编辑
    @ViewChild('flexaction') flexAction: FlexActionComponent; // 动作编辑
    
    property: GaugeProperty | WidgetProperty;
    withBitmask: boolean;   // 是否支持位掩码
}
```

**面板分组**:
1. **FlexHead** — 属性头部，根据 dialogType 显示不同内容:
   - `PropertyType.input` → 输入属性
   - `PropertyType.output` → 输出属性
   - `PropertyType.range` → 范围映射（默认）
   - `PropertyType.text` → 文字引用
   - `PropertyType.step` → 步进属性
   - `PropertyType.minmax` → 最小最大值

2. **FlexEvent** — 事件编辑器（可折叠）

3. **FlexAction** — 动作编辑器（可折叠）

### 3. 数据绑定配置 UI 结构

**保存流程**:
```typescript
onOkClick() {
    if (this.isWidget()) {
        this.data.settings.property = this.property;
    } else {
        this.data.settings.property = this.flexHead?.getProperty();
    }
    if (this.flexEvent) {
        this.data.settings.property.events = this.flexEvent.getEvents();
    }
    if (this.flexAction) {
        this.data.settings.property.actions = this.flexAction.getActions();
    }
}
```

### 4. 值处理编辑 UI

**Ranges**: `GaugeRangeProperty[]` — 每个范围包含 min/max/color/text/stroke/type/style
**Actions**: `GaugeAction[]` — 每个动作包含 variableId/bitmask/range/type/options
**Events**: `GaugeEvent[]` — 每个事件包含 type/action/actparam/actoptions

---

## 七、关键架构总结

### 编辑器架构（双层架构）

```
┌─────────────────────────────────────────┐
│  EditorComponent (Angular)               │
│  ├── 模板: 左侧工具栏 + 右侧属性面板      │
│  ├── 胶水层: 连接 SVG-Edit ↔ Angular      │
│  └── GaugeSettings 管理                  │
│       ┌──────────────────────────┐       │
│       │ svgEditor (原生JS)       │       │
│       │ ├── svgcanvas.js        │       │
│       │ │   ├── mousedown       │       │
│       │ │   ├── mousemove        │       │
│       │ │   ├── mouseup          │       │
│       │ │   ├── rubber-band      │       │
│       │ │   ├── resize handles   │       │
│       │ │   ├── undo/redo stack  │       │
│       │ │   └── group/ungroup    │       │
│       │ ├── select.js           │       │
│       │ ├── draw.js             │       │
│       │ └── contextmenu.js      │       │
│       └──────────────────────────┘       │
└─────────────────────────────────────────┘
```

### 运行时架构（数据绑定链路）

```
WebSocket/SSE
    ↓
HmiService.onVariableChanged
    ↓
GaugesManager.onchange.emit(sig)
    ↓
FuxaViewComponent.handleSignal(sig)
    ↓
GaugesManager.getGaugeSettings(viewId, sigId)  → 找到绑定 gauge
    ↓
GaugesManager.processValue(gaugeSettings, svgElement, signal, gaugeStatus)
    ↓
按类型分发 → XxxComponent.processValue()  → 修改 SVG DOM 属性
```

### 对我们项目的移植启示

1. **画布引擎**: FUXA 使用 SVG-Edit (一个成熟的 SVG 编辑器库)，不是自己从零实现
2. **渲染方式**: innerHTML 直接注入 SVG 字符串 + SVG.js 操作 DOM
3. **数据绑定**: GaugeSettings 字典 → 信号订阅 → processValue 分发 → 修改 SVG 属性
4. **控件嵌入**: 通过 Angular 动态组件在 foreignObject 中渲染 HTML 控件
5. **属性编辑**: 独立的对话框/侧边栏组件，按控件类型分发不同的属性编辑器
