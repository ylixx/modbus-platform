import type { MouseTouchEvent } from '../../../../components/mt-dzr/utils/types';
import type { IDoneJson, IGlobalStoreCanvasCfg, IGlobalStoreGridCfg } from '../../store/types';
type LineRenderProps = {
    itemJson: IDoneJson;
    canvasCfg: IGlobalStoreCanvasCfg;
    grid: IGlobalStoreGridCfg;
    canvasDom: HTMLElement | null;
    mode: 'pen' | 'pencil';
};
declare const _default: import("vue").DefineComponent<__VLS_WithDefaults<__VLS_TypePropsToRuntimeProps<LineRenderProps>, {
    mode: string;
}>, {
    onMouseDown: (de: MouseTouchEvent, point_index: number, item: {
        x: number;
        y: number;
    }) => void;
}, unknown, {}, {}, import("vue").ComponentOptionsMixin, import("vue").ComponentOptionsMixin, {
    drawLineEnd: (...args: any[]) => void;
}, string, import("vue").VNodeProps & import("vue").AllowedComponentProps & import("vue").ComponentCustomProps, Readonly<import("vue").ExtractPropTypes<__VLS_WithDefaults<__VLS_TypePropsToRuntimeProps<LineRenderProps>, {
    mode: string;
}>>> & {
    onDrawLineEnd?: ((...args: any[]) => any) | undefined;
}, {
    mode: "pen" | "pencil";
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
