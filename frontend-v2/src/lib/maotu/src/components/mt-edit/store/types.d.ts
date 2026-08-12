export type ILeftAsideConfig = Map<string, ILeftAsideConfigItem[]>;
export type ILeftAsideConfigItemPublicPropsType = 'input' | 'color' | 'select' | 'switch' | 'number' | 'jsonEdit' | 'textArea';
export type ILeftAsideConfigItemPublicProps = Record<string, {
    title: string;
    type: ILeftAsideConfigItemPublicPropsType;
    val: any;
    options?: any;
    disabled?: boolean;
}>;
export type ILeftAsideConfigItemPublicType = 'svg' | 'vue' | 'img' | 'custom-svg';
export type ILeftAsideConfigItemPrivateType = 'group' | 'sys-line';
export interface ILeftAsideConfigItemPublic {
    id: string;
    title: string;
    type: ILeftAsideConfigItemPublicType | ILeftAsideConfigItemPrivateType;
    thumbnail: string;
    svg?: string;
    props: ILeftAsideConfigItemPublicProps;
}
export interface ILeftAsideConfigItemPrivateSymbol {
    symbol_id: string;
    symbol_str: string;
    width: string;
    height: string;
}
export interface ICommonAnimations {
    val: string;
    delay: string;
    speed: string;
    repeat: string;
}
export interface ILeftAsideConfigItemPrivate {
    symbol?: ILeftAsideConfigItemPrivateSymbol;
    common_animations: ICommonAnimations;
}
export type ILeftAsideConfigItem = ILeftAsideConfigItemPublic & ILeftAsideConfigItemPrivate;
export type GlobalStoreIntention = 'none' | 'create' | 'beginMulSelect' | 'adsorbStart' | 'adsorbEnd' | 'beginDragCanvas' | 'runDragCanvas' | 'endDragCanvas' | 'showContextMenu' | 'drawSysLineStart';
export interface IGlobalStoreCreateItemInfo {
    config_key: string;
    item_id: string;
}
export interface IGlobalStoreCanvasCfg {
    width: number;
    height: number;
    scale: number;
    color: string;
    img: string;
    guide: boolean;
    adsorp: boolean;
    adsorp_diff: number;
    transform_origin: {
        x: number;
        y: number;
    };
    drag_offset: {
        x: number;
        y: number;
    };
}
export interface IGlobalStoreGridCfg {
    enabled: boolean;
    align: boolean;
    size: number;
}
export type DoneJsonEventListType = 'click' | 'dblclick' | 'mouseover' | 'mouseout';
export type DoneJsonEventListAction = 'changeAttr' | 'customCode';
export interface IDoneJsonActionChangeAttr {
    id: string;
    target_id: string;
    target_attr: string | undefined;
    target_value: any;
}
export interface IDoneJsonEventList {
    id: string;
    type: DoneJsonEventListType;
    action: DoneJsonEventListAction;
    change_attr: IDoneJsonActionChangeAttr[];
    custom_code: string;
    trigger_rule: {
        trigger_id?: string;
        trigger_attr?: string;
        operator?: string;
        value?: any;
    };
}
export interface IDoneJson {
    id: string;
    title: string;
    type: ILeftAsideConfigItemPublicType | ILeftAsideConfigItemPrivateType;
    symbol?: ILeftAsideConfigItemPrivateSymbol;
    binfo: IDoneJsonBinfo;
    props: ILeftAsideConfigItemPublicProps;
    resize: boolean;
    rotate: boolean;
    lock: boolean;
    active: boolean;
    hide: boolean;
    common_animations: ICommonAnimations;
    use_proportional_scaling?: boolean;
    children?: IDoneJson[];
    tag?: string;
    thumbnail?: string;
    events: IDoneJsonEventList[];
}
export interface IDoneJsonBinfo {
    left: number;
    top: number;
    width: number;
    height: number;
    angle: number;
}
export interface CacheBoundingBox {
    id: string;
    type: ILeftAsideConfigItemPublicType | ILeftAsideConfigItemPrivateType;
    left: number;
    top: number;
    width: number;
    height: number;
    bottom: number;
    right: number;
}
export type AdsorbPointType = 'tc' | 'bc' | 'lc' | 'rc';
export interface IContextMenuInfo {
    title: string;
    hot_key: string;
    enable: boolean;
}
export type ContextMenuInfoType = 'copy' | 'paste' | 'delete' | 'group' | 'ungroup' | 'selectAll' | 'moveTop' | 'moveUp' | 'moveDown' | 'moveBottom';
export interface IContextMenuDetail {
    left: number;
    top: number;
    info: {
        [key in ContextMenuInfoType]: IContextMenuInfo;
    };
}
export interface IRealTimeData {
    show: boolean;
    text: string;
}
export interface IGlobalStore {
    intention: GlobalStoreIntention;
    create_item_info: IGlobalStoreCreateItemInfo | null;
    done_json: IDoneJson[];
    selected_items_id: string[];
    canvasCfg: IGlobalStoreCanvasCfg;
    gridCfg: IGlobalStoreGridCfg;
    guideCfg: {
        x: {
            display: boolean;
            top: number;
        };
        y: {
            display: boolean;
            left: number;
        };
    };
    lock: boolean;
    real_time_data: IRealTimeData;
    adsorp_diff: {
        x: number;
        y: number;
    };
    setIntention: (val: GlobalStoreIntention) => void;
    setCreateItemInfo: (val: IGlobalStoreCreateItemInfo | null) => void;
    setGlobalStoreDoneJson: (val: IDoneJson[]) => void;
    cancelAllSelect: () => void;
    refreshSelectedItemsId: () => void;
    deleteSelectedItems: () => void;
    setSingleSelect: (id: string) => void;
    setSelectItems: (ids: string[]) => void;
    setRealTimeData: (val: IRealTimeData) => void;
}
export interface ILeftAside {
    config: ILeftAsideConfig;
    registerConfig: (title: string, config: ILeftAsideConfigItemPublic[]) => void;
}
export interface ICache {
    boundingBox: CacheBoundingBox[];
    setBoundingBox: (val: CacheBoundingBox[]) => void;
    adsorbPoint: {
        type: AdsorbPointType;
        x: number;
        y: number;
        id: string;
    }[];
    setAdsorbPoint: (val: {
        type: AdsorbPointType;
        x: number;
        y: number;
        id: string;
    }[]) => void;
    copy: IDoneJson[];
    setCopy: (val: IDoneJson[]) => void;
    history: IDoneJson[][];
    historyIndex: number;
    addHistory: (done_json: IDoneJson[]) => void;
}
export interface IConfig {
    sysComponent: ILeftAsideConfigItem[];
    lineRenderOffset: number;
}
/**
 * 右键菜单
 */
export interface IContextMenu {
    menuInfo: IContextMenuDetail;
    setMenuInfo: (val: IContextMenuDetail) => void;
    setDisplayItem: (val: ContextMenuInfoType[]) => void;
}
