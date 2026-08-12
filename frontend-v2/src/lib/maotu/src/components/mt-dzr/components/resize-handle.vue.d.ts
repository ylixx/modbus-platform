import type { IDzrPropsModelValue } from '../types';
type ResizeProps = {
    itemInfo: IDzrPropsModelValue;
    targetDom: HTMLElement | null;
    scaleRatio: number;
    gridAlignSize: number;
    genId: string;
    useProportionalScaling?: boolean;
};
declare const _default: import("vue").DefineComponent<__VLS_WithDefaults<__VLS_TypePropsToRuntimeProps<ResizeProps>, {
    scaleRatio: number;
    gridAlignSize: number;
    useProportionalScaling: boolean;
}>, {}, unknown, {}, {}, import("vue").ComponentOptionsMixin, import("vue").ComponentOptionsMixin, {
    "update:itemInfo": (...args: any[]) => void;
    onResizeDone: (...args: any[]) => void;
    onResizeMove: (...args: any[]) => void;
}, string, import("vue").VNodeProps & import("vue").AllowedComponentProps & import("vue").ComponentCustomProps, Readonly<import("vue").ExtractPropTypes<__VLS_WithDefaults<__VLS_TypePropsToRuntimeProps<ResizeProps>, {
    scaleRatio: number;
    gridAlignSize: number;
    useProportionalScaling: boolean;
}>>> & {
    "onUpdate:itemInfo"?: ((...args: any[]) => any) | undefined;
    onOnResizeDone?: ((...args: any[]) => any) | undefined;
    onOnResizeMove?: ((...args: any[]) => any) | undefined;
}, {
    scaleRatio: number;
    gridAlignSize: number;
    useProportionalScaling: boolean;
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
