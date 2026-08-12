import type { IDoneJson, IGlobalStoreCanvasCfg, IGlobalStoreGridCfg } from '../../store/types';
type LineRenderProps = {
    itemJson: IDoneJson;
    canvasCfg: IGlobalStoreCanvasCfg;
    grid: IGlobalStoreGridCfg;
    canvasDom: HTMLElement | null;
    doneJson: IDoneJson[];
    lockState: boolean;
    mode: 'normal' | 'line-edit';
};
declare const _default: import("vue").DefineComponent<__VLS_WithDefaults<__VLS_TypePropsToRuntimeProps<LineRenderProps>, {
    mode: string;
}>, {}, unknown, {}, {}, import("vue").ComponentOptionsMixin, import("vue").ComponentOptionsMixin, {
    setIntention: (...args: any[]) => void;
    "update:itemJson": (...args: any[]) => void;
    lineMouseUp: (...args: any[]) => void;
}, string, import("vue").VNodeProps & import("vue").AllowedComponentProps & import("vue").ComponentCustomProps, Readonly<import("vue").ExtractPropTypes<__VLS_WithDefaults<__VLS_TypePropsToRuntimeProps<LineRenderProps>, {
    mode: string;
}>>> & {
    onSetIntention?: ((...args: any[]) => any) | undefined;
    "onUpdate:itemJson"?: ((...args: any[]) => any) | undefined;
    onLineMouseUp?: ((...args: any[]) => any) | undefined;
}, {
    mode: "normal" | "line-edit";
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
