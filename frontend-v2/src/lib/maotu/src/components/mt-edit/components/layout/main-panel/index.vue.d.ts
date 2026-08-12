type MainPanelProps = {
    groupEnabled: boolean;
    unGroupEnabled: boolean;
    deleteEnabled: boolean;
    lineAppendEnable?: boolean;
};
declare const _default: import("vue").DefineComponent<__VLS_WithDefaults<__VLS_TypePropsToRuntimeProps<MainPanelProps>, {
    lineAppendEnable: boolean;
}>, {
    createGroupItem: () => void;
    onUngroup: () => void;
    onAlignSelected: (type: "left" | "top" | "horizontally" | "right" | "vertically" | "bottom" | "horizontal-distribution" | "vertical-distribution") => void;
    onRedo: () => void;
    onUndo: () => void;
    beginListenerKeyDown: () => void;
    stopListenerKeyDown: () => void;
}, unknown, {}, {}, import("vue").ComponentOptionsMixin, import("vue").ComponentOptionsMixin, {}, string, import("vue").VNodeProps & import("vue").AllowedComponentProps & import("vue").ComponentCustomProps, Readonly<import("vue").ExtractPropTypes<__VLS_WithDefaults<__VLS_TypePropsToRuntimeProps<MainPanelProps>, {
    lineAppendEnable: boolean;
}>>>, {
    lineAppendEnable: boolean;
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
