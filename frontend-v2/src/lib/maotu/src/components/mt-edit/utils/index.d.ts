import type { MoveItemBoundingInfo } from '../components/render-core/types';
import type { CacheBoundingBox, IDoneJson, IDoneJsonBinfo, ILeftAsideConfigItemPublicProps } from '../store/types';
export declare const createGroupInfo: (selected_items: IDoneJson[], canvas_dom: HTMLElement, scale_ratio: number) => IDoneJson;
/**
 * 取消组合
 * @param elements 元素列表
 * @param editorRect 画布react信息
 * @returns 拆分后的列表
 */
export declare const cancelGroup: (selected_item: IDoneJson, canvas_dom: HTMLElement, scale_ratio: number, grid_align_size: number) => {
    active: boolean;
    binfo: {
        width: number;
        height: number;
        left: number;
        top: number;
        angle: number;
    };
    id: string;
    title: string;
    type: import("../store/types").ILeftAsideConfigItemPublicType | import("../store/types").ILeftAsideConfigItemPrivateType;
    symbol?: import("../store/types").ILeftAsideConfigItemPrivateSymbol | undefined;
    props: ILeftAsideConfigItemPublicProps;
    resize: boolean;
    rotate: boolean;
    lock: boolean;
    hide: boolean;
    common_animations: import("../store/types").ICommonAnimations;
    use_proportional_scaling?: boolean | undefined;
    children?: IDoneJson[] | undefined;
    tag?: string | undefined;
    thumbnail?: string | undefined;
    events: import("../store/types").IDoneJsonEventList[];
}[];
export declare const svgToSymbol: (svgStr: string, id: string) => {
    symbol_str: string;
    width: string;
    height: string;
};
export declare const symbolGenSvg: (symbol_id: string, symbol_str: string, width: string, height: string, props_str: string) => string;
export declare const svgToImgSrc: (svgStr: string) => string;
/**
 * 生成dom可用的属性字符串
 * @param props
 * @returns
 */
export declare const genDomPropstr: (props: ILeftAsideConfigItemPublicProps) => string;
/**
 * 生成随机字符串
 * @param len 生成个数
 */
export declare const randomString: (len?: number) => string;
/**
 * 获取当前点击坐标 根据pc端和移动端获取
 * @param e
 * @returns
 */
export declare function getRealityXY(e: DragEvent | TouchEvent | MouseEvent, canvas_dom_rect: DOMRect | undefined): {
    realityX: number;
    realityY: number;
};
export declare const blobToBase64: (file: Blob) => Promise<unknown>;
/**
 * 根据坐标对齐到网格
 * @param position 当前坐标
 * @param grid 网格大小
 * @returns 对应网格的坐标
 */
export declare const alignToGrid: (position: number, grid?: number) => number;
/**
 * json对象深拷贝
 * @param object
 * @param default_val
 * @returns
 */
export declare const objectDeepClone: <T>(object: object, default_val?: any) => T;
export declare const prosToVBind: (item: ILeftAsideConfigItemPublicProps) => {};
/**
 * 计算y轴参考线属性和需要吸附的偏移距离
 * @param cacheStore_boundingBox
 * @param adsorp_diff
 * @param move_item_bounding_info
 */
export declare const calculateGuideY: (cacheStore_boundingBox: CacheBoundingBox[], adsorp_diff: number, move_item_bounding_info: MoveItemBoundingInfo[], canvas_bounding_info: DOMRect, scale: number) => {
    y_info: {
        display: boolean;
        left: number;
    };
    move_x: number;
};
/**
 * 计算x轴参考线属性和需要吸附的偏移距离
 * @param cacheStore_boundingBox
 * @param adsorp_diff
 * @param move_item_bounding_info
 */
export declare const calculateGuideX: (cacheStore_boundingBox: CacheBoundingBox[], adsorp_diff: number, move_item_bounding_info: MoveItemBoundingInfo[], canvas_bounding_info: DOMRect, scale: number) => {
    x_info: {
        display: boolean;
        top: number;
    };
    move_y: number;
};
/**
 * 坐标数组转换成path路径
 * @param position_arr
 * @returns
 */
export declare const positionArrarToPath: (position_arr: {
    x: number;
    y: number;
}[], offset_x?: number, offset_y?: number) => string;
/**
 * 取两点之间坐标
 * @param x1
 * @param y1
 * @param x2
 * @param y2
 * @returns
 */
export declare const getCenterXY: (x1: number, y1: number, x2: number, y2: number) => {
    x: number;
    y: number;
};
/**
 * 计算旋转之后的坐标
 * @param x 旋转之前x坐标
 * @param y 旋转之前y坐标
 * @param centerX 旋转中心x坐标
 * @param centerY 旋转中心y坐标
 * @param angleRad 旋转角度
 * @returns 旋转之后的xy坐标
 */
export declare const rotatePoint: (x: number, y: number, centerX: number, centerY: number, angleRad: number) => {
    x: number;
    y: number;
};
export declare const getRectCoordinate: (item: IDoneJsonBinfo) => {
    topLeft: {
        x: number;
        y: number;
    };
    topRight: {
        x: number;
        y: number;
    };
    bottomLeft: {
        x: number;
        y: number;
    };
    bottomRight: {
        x: number;
        y: number;
    };
};
export declare const getRectCenterCoordinate: (topLeft: {
    x: any;
    y: any;
}, topRight: {
    x: any;
    y: any;
}, bottomLeft: {
    x: any;
    y: any;
}, bottomRight: {
    x: any;
    y: any;
}) => {
    topCenter: {
        x: number;
        y: number;
    };
    bottomCenter: {
        x: number;
        y: number;
    };
    leftCenter: {
        x: number;
        y: number;
    };
    rightCenter: {
        x: number;
        y: number;
    };
};
export declare const handleAlign: (type: 'left' | 'horizontally' | 'right' | 'top' | 'vertically' | 'bottom' | 'horizontal-distribution' | 'vertical-distribution', selected_done_json: IDoneJson[], canvasDom: HTMLElement, scale: number, global_done_json: IDoneJson[]) => IDoneJson[];
/**
 * 设置图形属性
 * @param id
 * @param key
 * @param val
 * @param json_arr
 * @returns
 */
export declare const setItemAttr: (id: string, key: string, val: any, json_arr: IDoneJson[]) => Promise<unknown>;
export declare const getItemAttr: (id: string, key: string, json_arr: IDoneJson[]) => any;
export declare const previewCompareVal: (val1: any, operator: '>' | '<' | '=' | '!=', val2: any) => boolean;
/**
 * 将事件转换成v-on
 * @param item
 * @returns
 */
export declare const eventToVOn: (item: IDoneJson) => {};
