# FUXA SCADA 编辑器架构深度分析报告

## 一、技术栈总览

| 层面 | 技术 |
|------|------|
| 框架 | Angular (TypeScript) |
| 画布绘制 | **原生 SVG**（非 Canvas、非 Fabric.js） |
| SVG 操作库 | **SVG.js** (`declare var SVG: any`) |
| 动画引擎 | SVG.js 内置动画 + setInterval 手动动画 |
| UI 组件库 | Angular Material |
| 拖拽/缩放 | angular-gridster2（Cards 布局）、ngDraggable、ngResizable |
| 图表 | uPlot (ngx-uplot) |
| 仪表盘 | ngx-gauge |
| 滑块 | ngx-nouislider (noUiSlider) |
| 触摸键盘 | ngx-touch-keyboard |

**核心结论：FUXA 使用原生 SVG 作为画布，配合 SVG.js 库进行 DOM 操作和动画。不使用 Canvas、不使用 Fabric.js。**

---

## 二、核心架构层次

```
┌─────────────────────────────────────────────────────────┐
│                    app.component.ts                      │
│                  (根组件，路由出口)                        │
├─────────────────────────────────────────────────────────┤
│  editor/                          fuxa-view/             │
│  ┌──────────────────────┐        ┌────────────────────┐ │
│  │ editor.component.ts   │        │ fuxa-view.component│ │
│  │ (编辑器主组件 65KB)    │◄──────►│ .ts (运行时视图渲染 │ │
│  │ editor.component.html │        │   53KB)            │ │
│  │ (编辑器布局 82KB)      │        │ fuxa-view.component│ │
│  │                        │        │ .html (3KB)        │ │
│  └──────────────────────┘        └────────────────────┘ │
├─────────────────────────────────────────────────────────┤
│                   gauges/gauges.component.ts             │
│                 (GaugesManager - 图元引擎 46KB)          │
├─────────────────────────────────────────────────────────┤
│  gauges/shapes/          gauges/controls/                │
│  ┌────────────────┐     ┌──────────────────┐           │
│  │ shapes.component│     │ value/           │           │
│  │ (基础形状)       │     │ html-input/      │           │
│  │                 │     │ html-button/     │           │
│  │ ape-shapes/     │     │ html-select/     │           │
│  │ (动画工艺图元)   │     │ html-chart/      │           │
│  │                 │     │ html-graph/      │           │
│  │ proc-eng/       │     │ gauge-progress/  │           │
│  │ (工艺工程图元)   │     │ gauge-semaphore/ │           │
│  │                 │     │ pipe/            │           │
│  └────────────────┘     │ slider/          │           │
│                         │ html-switch/     │           │
│                         │ html-iframe/     │           │
│                         │ html-table/      │           │
│                         │ html-image/      │           │
│                         │ html-video/      │           │
│                         │ html-scheduler/  │           │
│                         │ panel/           │           │
│                         └──────────────────┘           │
├─────────────────────────────────────────────────────────┤
│  _models/hmi.ts    _helpers/svg-utils.ts                │
│  (数据模型 18KB)    (SVG工具 12KB)                       │
└─────────────────────────────────────────────────────────┘
```

---

## 三、画布渲染引擎详解

### 3.1 SVG 画布核心原理

FUXA 的"画布"本质是一个 **SVG 文档**，存储为 `View.svgcontent` 字符串。

**关键代码流程** (`fuxa-view.component.ts:loadResolvedHmi`):

```typescript
// 将 SVG 字符串直接注入到 DOM 的 div 容器中
this.dataContainer.nativeElement.innerHTML = view.svgcontent.replace('<title>Layer 1</title>', '');
```

这意味着：
- View（视图）的整个内容就是一个完整的 SVG 文档字符串
- 渲染时直接将 SVG 字符串作为 `innerHTML` 插入 DOM
- 所有图元都是 SVG DOM 元素，可以通过标准 DOM API 操作
- 使用 **SVG.js** (`SVG.adopt()`) 包装原生 DOM 节点，提供动画和变换能力

### 3.2 SVG.js 的使用模式

```typescript
declare var SVG: any;

// 获取 SVG 元素并包装为 SVG.js 对象
let element = SVG.adopt(svgele.node);

// 动画旋转
element.animate(3000).ease('-').rotate(360).loop();

// 动画移动
element.animate(500).ease('-').move(x, y);

// 变换
element.animate(200).ease('-').transform({ rotate: rotation });

// 显隐
element.show() / element.hide();
```

### 3.3 View 渲染流程

```
loadHmi(view) → loadResolvedHmi(view) → 
  1. innerHTML = view.svgcontent  (SVG字符串注入DOM)
  2. loadWatch(view)              (绑定图元+信号)
     ↓
  对 view.items 中每个 GaugeSettings:
  3. gaugesManager.initElementAdded()   (初始化图元)
  4. gaugesManager.bindGauge()          (绑定信号和事件)
  5. 处理初始值 → processValue()         (渲染数据绑定)
     ↓
  6. hmiService.viewsTagsSubscribe()    (订阅WebSocket实时数据)
     ↓
  7. handleSignal() → processValue()    (收到数据更新图元)
```

---

## 四、图元（Gauge）系统架构

### 4.1 图元类型注册表

`GaugesManager.Gauges` 静态数组定义了所有图元类型：

| 图元 | TypeTag | 类别 | 说明 |
|------|---------|------|------|
| ValueComponent | `svg-ext-value` | 控件 | 文本值显示 |
| HtmlInputComponent | `svg-ext-input` | 控件 | 输入框 |
| HtmlButtonComponent | `svg-ext-button` | 控件 | 按钮 |
| HtmlBagComponent | `svg-ext-gauge` | 控件 | 仪表盘 (ngx-gauge) |
| HtmlSelectComponent | `svg-ext-select` | 控件 | 下拉选择 |
| HtmlChartComponent | `svg-ext-chart` | 控件 | 图表 (uPlot) |
| HtmlGraphComponent | `svg-ext-graph` | 控件 | 趋势图 |
| GaugeProgressComponent | `svg-ext-progress` | 控件 | 进度条 |
| GaugeSemaphoreComponent | `svg-ext-led` | 控件 | LED指示灯 |
| ShapesComponent | `svg-ext-shapes` | 形状 | 通用形状（旋转/移动/闪烁） |
| ProcEngComponent | (proc-eng) | 形状 | 工艺工程图元 |
| ApeShapesComponent | `svg-ext-ape` | 形状 | 动画工艺图元（电机/活塞） |
| PipeComponent | (pipe) | 控件 | 管道 |
| SliderComponent | (slider) | 控件 | 滑块 |
| HtmlSwitchComponent | (switch) | 控件 | 开关 |
| HtmlIframeComponent | (iframe) | 控件 | 内嵌网页 |
| HtmlTableComponent | (table) | 控件 | 数据表格 |
| HtmlImageComponent | (image) | 控件 | 图片 |
| PanelComponent | (panel) | 控件 | 嵌入式子视图 |
| HtmlVideoComponent | (video) | 控件 | 视频 |
| HtmlSchedulerComponent | (scheduler) | 控件 | 排程器 |

### 4.2 图元在 SVG 中的表示

图元在 SVG 文档中以 **`<div>` 占位符**形式存在（对Angular动态组件），
或直接作为 **SVG 图形元素**（对 Shapes 类图元）：

```svg
<!-- 一个按钮图元 -->
<div id="gauge_123" type="svg-ext-button" 
     style="left:100px;top:200px;width:80px;height:40px;">
</div>

<!-- 一个形状图元 -->
<g id="shape_456" type="svg-ext-shapes">
  <rect x="10" y="20" width="100" height="60" fill="green"/>
</g>

<!-- 一个动画工艺图元 -->
<g id="ape_789" type="svg-ext-ape">
  <circle cx="50" cy="50" r="30" class="pm"/>
</g>
```

**关键发现**：`type` 属性是图元类型识别的核心标识符。
- `GaugesManager.isGauge(type)` 通过检查 type 是否以 `svg-ext-` 开头来判断
- `processValue()` 根据 type 路由到对应的静态处理方法

### 4.3 图元数据模型

```typescript
// 核心数据结构
class GaugeSettings {
    id: string;        // SVG元素 ID
    type: string;      // 图元类型标签 (如 'svg-ext-shapes')
    name: string;      // 名称
    label: string;     // 显示标签
    property: GaugeProperty;  // 属性（数据绑定+事件+动作）
    hide: boolean;     // 是否隐藏
    lock: boolean;     // 是否锁定
}

class GaugeProperty {
    variableId: string;        // 绑定的变量/Tag ID
    variableValue: string;     // 初始值
    bitmask: number;           // 位掩码
    permission: number;        // 权限
    ranges: GaugeRangeProperty[]; // 范围颜色映射
    events: GaugeEvent[];      // 事件（click, dblclick等）
    actions: GaugeAction[];    // 动作（hide, show, blink, rotate等）
    readonly: boolean;
}
```

---

## 五、数据绑定与实时渲染

### 5.1 信号订阅流程

```
1. loadWatch() 遍历 view.items
2. 对每个图元调用 gaugesManager.bindGauge()
3. bindGauge() → hmiService.addSignalGaugeToMap(viewId, signalId, gauge)
4. hmiService.viewsTagsSubscribe(signalIds) → WebSocket 订阅
5. 收到数据 → hmiService.onVariableChanged → GaugesManager.onchange
6. fuxa-view handleSignal(sig) → 查找绑定该信号的所有图元
7. gaugesManager.processValue(gaugeSetting, svgele, sig, gaugeStatus)
8. 根据 type 路由到具体的 processValue 静态方法
```

### 5.2 值处理与颜色映射

```typescript
// ShapesComponent.processValue 核心逻辑：
let value = parseFloat(sig.value);

// 1. 位掩码处理
let propValue = GaugeBaseComponent.checkBitmask(property.bitmask, value);

// 2. 范围颜色映射 (ranges)
if (ga.property.ranges) {
    for (range of ranges) {
        if (range.min <= propValue && range.max >= propValue) {
            propertyColor.fill = range.color;
            propertyColor.stroke = range.stroke;
        }
    }
    // 遍历SVG DOM树设置 fill/stroke
    GaugeBaseComponent.walkTreeNodeToSetAttribute(node, 'fill', color);
    GaugeBaseComponent.walkTreeNodeToSetAttribute(node, 'stroke', color);
}

// 3. 动作处理 (actions)
if (ga.property.actions) {
    actions.forEach(act => {
        if (isActionSignal(act, sig.id)) {
            processAction(act, svgele, value, gaugeStatus);
        }
    });
}
```

### 5.3 动作类型

| 动作 | 说明 | 实现 |
|------|------|------|
| hide | 隐藏图元 | element.hide() |
| show | 显示图元 | element.show() |
| blink | 闪烁 | 定时器切换 fill/stroke 颜色 |
| clockwise | 顺时针旋转 | SVG.js animate rotate(360).loop() |
| anticlockwise | 逆时针旋转 | animate rotate(-360).loop() |
| rotate | 角度旋转 | 按值范围映射到角度 |
| move | 移动 | animate move(toX, toY) |
| moveByTags | 按Tag值移动 | 值到像素的线性映射 |
| stop | 停止动画 | 清除定时器 |
| downup | 上下运动 | 活塞式往复运动 (ApeShapes) |

---

## 六、编辑器组件详解

### 6.1 editor.component（编辑器主组件）

- **文件大小**：TS 65KB + HTML 82KB + CSS 16KB = 共约 163KB
- 这是 FUXA 最大的组件，包含：
  - SVG 绘图编辑器（基于 SVG.js + 自定义编辑逻辑）
  - 左侧工具栏（形状/控件拖拽面板）
  - 右侧属性面板（layout-property, view-property）
  - 图形选择器 (svg-selector)
  - 视图管理 (editor-views-list)

### 6.2 编辑器子组件

| 子组件 | 路径 | 功能 |
|--------|------|------|
| layout-property | editor/layout-property/ | 布局属性编辑 |
| view-property | editor/view-property/ | 视图属性编辑 |
| svg-selector | editor/svg-selector/ | SVG符号选择器 |
| editor-views-list | editor/editor-views-list/ | 视图列表管理 |
| tags-ids-config | editor/tags-ids-config/ | Tag/变量绑定配置 |
| graph-config | editor/graph-config/ | 图表配置 |
| chart-config | editor/chart-config/ | 趋势图配置 |
| card-config | editor/card-config/ | 卡片配置 |
| app-settings | editor/app-settings/ | 应用设置 |
| setup | editor/setup/ | 初始设置向导 |
| onboarding-wizard | editor/onboarding-wizard/ | 引导向导 |

---

## 七、Widget/自定义脚本系统

### 7.1 Widget 属性模型

```typescript
class WidgetProperty extends GaugeProperty {
    type: string;
    scriptContent?: { moduleId: string, content: string };
    svgContent?: string;
    varsToBind?: WidgetPropertyVariable[] = [];
}

interface WidgetPropertyVariable {
    originalName: string;   // 原始变量名
    name: string;           // 重命名后的名称（带前缀）
    type: string;           // 'boolean' | 'number' | 'string' | 'color'
    variableId?: string;    // 绑定的Tag ID
    variableValue?: string; // 值
}
```

### 7.2 变量命名约定（WidgetPropertyVariableTypePrefix）

```typescript
enum WidgetPropertyVariableTypePrefix {
    boolean = '_pb_',   // _pb_myFlag
    number = '_pn_',    // _pn_myValue
    string = '_ps_',    // _ps_myText
    color = '_pc_',     // _pc_myColor
}
```

### 7.3 脚本处理流程 (svg-utils.ts)

```
1. removeComments()          → 移除 /* */ 注释
2. exportGlobalVariables()   → 提取 //!export-start...//!export-end 区间
3. exportFunctionNames()     → 导出函数名到模块对象
4. replaceIdsInScript()      → 替换 SVG ID 引用
5. addModuleDeclaration()    → 包装为 IIFE: var moduleId = {}; (function(){...})(); window.moduleId=moduleId
```

这种设计允许用户在 Widget 中编写 JavaScript 脚本，通过 `postValue()` 与外部通信，
系统会自动重命名变量/函数避免冲突。

---

## 八、View 类型系统

```typescript
enum ViewType {
    svg = 'svg',       // SVG 画布视图（主要类型）
    cards = 'cards',   // 卡片网格视图 (angular-gridster2)
    maps = 'maps'      // 地图视图
}
```

### SVG View 结构

```typescript
class View {
    id: string;              // 唯一ID
    name: string;            // 视图名称
    profile: DocProfile;     // 画布尺寸/背景
    items: DictionaryGaugeSettings;  // 图元配置字典
    variables: DictionaryVariables;  // 变量字典
    svgcontent: string;      // ★ SVG 文档字符串（核心）
    type: ViewType;          // 视图类型
    property: ViewProperty;  // 视图级事件
}

class DocProfile {
    width = 1024;
    height = 768;
    bkcolor = '#ffffffff';
    margin = 10;
    align = DocAlignType.topCenter;
    gridType: GridType = GridType.Fixed;
    viewRenderDelay = 0;
}
```

---

## 九、关键架构特征总结

### 9.1 核心设计决策

1. **SVG 作为画布**：所有图元都是 SVG DOM 元素，SVG 字符串即视图持久化格式
2. **innerHTML 渲染**：直接将 SVG 字符串注入 DOM，零虚拟DOM开销
3. **SVG.js 操作层**：在原生 DOM 之上提供动画、变换等高级 API
4. **静态方法模式**：所有图元的 `processValue`、`getSignals` 等都是静态方法，
   由 `GaugesManager` 根据类型标签路由调用
5. **类型标签识别**：通过 SVG 元素的 `type` 属性识别图元类型（如 `svg-ext-shapes`）

### 9.2 与 Fabric.js 方案对比

| 特性 | FUXA (SVG.js) | Fabric.js 方案 |
|------|---------------|----------------|
| 渲染方式 | SVG DOM | Canvas 2D |
| 对象模型 | SVG 元素 = DOM 节点 | JS 对象 → Canvas 绘制 |
| 持久化 | SVG 字符串直接存储 | JSON 序列化 |
| CSS 样式 | 原生支持 | 不支持 |
| 事件绑定 | DOM 原生事件 | 手动 hit-test |
| 文本渲染 | 浏览器原生 | 手动测量 |
| 性能上限 | 中等（DOM 节点数限制） | 高（像素级渲染） |
| 可访问性 | 支持（DOM 语义） | 不支持 |

### 9.3 数据流向图

```
┌──────────┐  WebSocket  ┌───────────┐  subscribe  ┌──────────────┐
│  Backend  │─────────────►│ HmiService │◄────────────│ GaugesManager │
│ (Node.js) │             └───────────┘             │ (信号→图元映射) │
└──────────┘                   │                    └───────┬────────┘
                               │ onVariableChanged           │
                               ▼                             │ processValue
                    ┌──────────────────┐                      │
                    │ FuxaViewComponent │◄─────────────────────┘
                    │  handleSignal()    │
                    └────────┬─────────┘
                             │ SVG DOM 操作
                             ▼
                    ┌──────────────────┐
                    │  SVG Document     │
                    │  (浏览器DOM树)    │
                    │ - <g type="svg-  │
                    │   ext-shapes">   │
                    │ - <div type="svg-│
                    │   ext-input">    │
                    └──────────────────┘
```

### 9.4 图元继承体系

```
GaugeBaseComponent (基类)
├── ShapesComponent (通用形状：颜色/闪烁/旋转/移动)
│   ├── ApeShapesComponent (动画工艺：电机/活塞)
│   └── ProcEngComponent (工艺工程形状)
├── ValueComponent (文本值)
├── HtmlInputComponent (输入框)
├── HtmlButtonComponent (按钮)
├── HtmlSelectComponent (下拉选择)
├── HtmlChartComponent (uPlot图表)
├── HtmlGraphComponent (趋势图)
├── GaugeProgressComponent (进度条)
├── GaugeSemaphoreComponent (LED指示灯)
├── PipeComponent (管道)
├── SliderComponent (滑块)
├── HtmlSwitchComponent (开关)
├── HtmlIframeComponent (内嵌网页)
├── HtmlTableComponent (数据表格)
├── HtmlImageComponent (图片)
├── PanelComponent (子视图面板)
├── HtmlVideoComponent (视频)
└── HtmlSchedulerComponent (排程器)
```

---

## 十、关键文件路径索引

| 文件 | GitHub 路径 | 大小 | 作用 |
|------|------------|------|------|
| hmi.ts | `_models/hmi.ts` | 18KB | 核心数据模型 |
| gauges.component.ts | `gauges/gauges.component.ts` | 46KB | 图元管理引擎 |
| fuxa-view.component.ts | `fuxa-view/fuxa-view.component.ts` | 53KB | 运行时视图渲染 |
| fuxa-view.component.html | `fuxa-view/fuxa-view.component.html` | 3KB | 视图模板 |
| editor.component.ts | `editor/editor.component.ts` | 66KB | 编辑器主逻辑 |
| editor.component.html | `editor/editor.component.html` | 82KB | 编辑器布局 |
| shapes.component.ts | `gauges/shapes/shapes.component.ts` | 12KB | 形状图元处理 |
| ape-shapes.component.ts | `gauges/shapes/ape-shapes/ape-shapes.component.ts` | 8KB | 动画工艺图元 |
| svg-utils.ts | `_helpers/svg-utils.ts` | 12KB | SVG/Widget工具 |
| utils.ts | `_helpers/utils.ts` | 26KB | 通用工具 |
| define.ts | `_helpers/define.ts` | 40KB | Material图标定义 |
| device.ts | `_models/device.ts` | 40KB | 设备/Tag模型 |
