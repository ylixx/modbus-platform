import type { IDoneJson, IGlobalStoreCanvasCfg, IGlobalStoreGridCfg } from '../../../../components/mt-edit/store/types';
type RenderCoreProps = {
    doneJson: IDoneJson[];
    canvasCfg: IGlobalStoreCanvasCfg;
    gridCfg: IGlobalStoreGridCfg;
    showGhostDom: boolean;
    canvasDom: HTMLElement | null;
    globalLock: boolean;
    preivewMode?: boolean;
    lineAppendEnable?: boolean;
    showPopover?: boolean;
};
declare const _default: import("vue").DefineComponent<__VLS_WithDefaults<__VLS_TypePropsToRuntimeProps<RenderCoreProps>, {
    doneJson: () => never[];
    showGhostDom: boolean;
    preivewMode: boolean;
    lineAppendEnable: boolean;
    showPopover: boolean;
}>, {}, unknown, {}, {}, import("vue").ComponentOptionsMixin, import("vue").ComponentOptionsMixin, {
    onMouseDown: (...args: any[]) => void;
    onItemMove: (...args: any[]) => void;
    onMoveMouseUp: (...args: any[]) => void;
    setIntention: (...args: any[]) => void;
    "update:doneJson": (...args: any[]) => void;
    onItemMouseEnter: (...args: any[]) => void;
    onItemMouseLeave: (...args: any[]) => void;
    onItemResizeDone: (...args: any[]) => void;
    onItemRotateDone: (...args: any[]) => void;
    onItemRightClick: (...args: any[]) => void;
}, string, import("vue").VNodeProps & import("vue").AllowedComponentProps & import("vue").ComponentCustomProps, Readonly<import("vue").ExtractPropTypes<__VLS_WithDefaults<__VLS_TypePropsToRuntimeProps<RenderCoreProps>, {
    doneJson: () => never[];
    showGhostDom: boolean;
    preivewMode: boolean;
    lineAppendEnable: boolean;
    showPopover: boolean;
}>>> & {
    onOnItemMove?: ((...args: any[]) => any) | undefined;
    onSetIntention?: ((...args: any[]) => any) | undefined;
    onOnMouseDown?: ((...args: any[]) => any) | undefined;
    onOnMoveMouseUp?: ((...args: any[]) => any) | undefined;
    "onUpdate:doneJson"?: ((...args: any[]) => any) | undefined;
    onOnItemMouseEnter?: ((...args: any[]) => any) | undefined;
    onOnItemMouseLeave?: ((...args: any[]) => any) | undefined;
    onOnItemResizeDone?: ((...args: any[]) => any) | undefined;
    onOnItemRotateDone?: ((...args: any[]) => any) | undefined;
    onOnItemRightClick?: ((...args: any[]) => any) | undefined;
}, {
    showGhostDom: boolean;
    doneJson: IDoneJson[];
    lineAppendEnable: boolean;
    preivewMode: boolean;
    showPopover: boolean;
}, {}>;
export default _default;
type __VLS_NonUndefinedable<T> = T extends undefined ? never : T;
type __VLS_TypePropsToRuntimeProps<T> = {
    [K in keyof T]-?: {} extends Pick<T, K> ? {
        type: import('vue').PropType<__VLS_NonUndefinedable<T[K]>>;
    } : {
        type: import('vue').PropType<T[K]>;
        required: true;
    };
};
type __VLS_WithDefaults<P, D> = {
    [K in keyof Pick<P, keyof P>]: K extends keyof D ? __VLS_Prettify<P[K] & {
        default: D[K];
    }> : P[K];
};
type __VLS_Prettify<T> = {
    [K in keyof T]: T[K];
} & {};
