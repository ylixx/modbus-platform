import { type IDzrProps, type IDzrPropsModelValue } from './types';
declare const _default: __VLS_WithTemplateSlots<import("vue").DefineComponent<__VLS_WithDefaults<__VLS_TypePropsToRuntimeProps<IDzrProps>, {
    id: string;
    modelValue: () => {
        left: number;
        top: number;
        width: number;
        height: number;
        angle: number;
    };
    scaleRatio: number;
    grid: () => {
        enabled: boolean;
        align: boolean;
        size: number;
    };
    resize: boolean;
    rotate: boolean;
    lock: boolean;
    active: boolean;
    useProportionalScaling: boolean;
    showGhostDom: boolean;
    hide: boolean;
    disabled: boolean;
    adsorp_diff: () => {
        x: number;
        y: number;
    };
}>, {}, unknown, {}, {}, import("vue").ComponentOptionsMixin, import("vue").ComponentOptionsMixin, {
    mousedown: (...args: any[]) => void;
    onResizeDone: (...args: any[]) => void;
    onResizeMove: (...args: any[]) => void;
    onRotateDone: (...args: any[]) => void;
    onRotateMove: (...args: any[]) => void;
    "update:modelValue": (...args: any[]) => void;
    onItemMove: (...args: any[]) => void;
    moveMouseUp: (...args: any[]) => void;
    onMouseEnter: (...args: any[]) => void;
    onMouseLeave: (...args: any[]) => void;
    onRightClick: (...args: any[]) => void;
}, string, import("vue").VNodeProps & import("vue").AllowedComponentProps & import("vue").ComponentCustomProps, Readonly<import("vue").ExtractPropTypes<__VLS_WithDefaults<__VLS_TypePropsToRuntimeProps<IDzrProps>, {
    id: string;
    modelValue: () => {
        left: number;
        top: number;
        width: number;
        height: number;
        angle: number;
    };
    scaleRatio: number;
    grid: () => {
        enabled: boolean;
        align: boolean;
        size: number;
    };
    resize: boolean;
    rotate: boolean;
    lock: boolean;
    active: boolean;
    useProportionalScaling: boolean;
    showGhostDom: boolean;
    hide: boolean;
    disabled: boolean;
    adsorp_diff: () => {
        x: number;
        y: number;
    };
}>>> & {
    onOnResizeDone?: ((...args: any[]) => any) | undefined;
    onOnResizeMove?: ((...args: any[]) => any) | undefined;
    onMousedown?: ((...args: any[]) => any) | undefined;
    onOnRotateDone?: ((...args: any[]) => any) | undefined;
    onOnRotateMove?: ((...args: any[]) => any) | undefined;
    "onUpdate:modelValue"?: ((...args: any[]) => any) | undefined;
    onOnItemMove?: ((...args: any[]) => any) | undefined;
    onMoveMouseUp?: ((...args: any[]) => any) | undefined;
    onOnMouseEnter?: ((...args: any[]) => any) | undefined;
    onOnMouseLeave?: ((...args: any[]) => any) | undefined;
    onOnRightClick?: ((...args: any[]) => any) | undefined;
}, {
    resize: boolean;
    scaleRatio: number;
    useProportionalScaling: boolean;
    id: string;
    modelValue: IDzrPropsModelValue;
    hide: boolean;
    grid: import("./types").IDzrPropsGrid;
    rotate: boolean;
    lock: boolean;
    active: boolean;
    showGhostDom: boolean;
    disabled: boolean;
    adsorp_diff: {
        x: number;
        y: number;
    };
}, {}>, {
    default?(_: {}): any;
}>;
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
type __VLS_WithTemplateSlots<T, S> = T & {
    new (): {
        $slots: S;
    };
};
