import type { MouseTouchEvent } from '../types';
type SelectedAreaProps = {
    scaleRatio: number;
    targetDom: HTMLElement | null;
};
declare const _default: import("vue").DefineComponent<__VLS_WithDefaults<__VLS_TypePropsToRuntimeProps<SelectedAreaProps>, {
    scaleRatio: number;
    targetDom: null;
}>, {
    onMouseDown: (de: MouseTouchEvent) => void;
}, unknown, {}, {}, import("vue").ComponentOptionsMixin, import("vue").ComponentOptionsMixin, {
    selectedAreaMouseUp: (...args: any[]) => void;
}, string, import("vue").VNodeProps & import("vue").AllowedComponentProps & import("vue").ComponentCustomProps, Readonly<import("vue").ExtractPropTypes<__VLS_WithDefaults<__VLS_TypePropsToRuntimeProps<SelectedAreaProps>, {
    scaleRatio: number;
    targetDom: null;
}>>> & {
    onSelectedAreaMouseUp?: ((...args: any[]) => any) | undefined;
}, {
    targetDom: HTMLElement | null;
    scaleRatio: number;
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
