import type { IExportJson } from '../mt-edit/components/types';
type MtPreviewProps = {
    exportJson?: IExportJson;
    canZoom?: boolean;
    canDrag?: boolean;
    showPopover?: boolean;
};
declare const _default: import("vue").DefineComponent<__VLS_WithDefaults<__VLS_TypePropsToRuntimeProps<MtPreviewProps>, {
    canDrag: boolean;
    canZoom: boolean;
    showPopover: boolean;
}>, {
    setItemAttrByID: (id: string, key: string, val: any) => Promise<unknown>;
    setImportJson: (exportJson: IExportJson) => boolean;
    setItemAttrs: (info: {
        id: string;
        key: string;
        val: any;
    }[]) => void;
}, unknown, {}, {}, import("vue").ComponentOptionsMixin, import("vue").ComponentOptionsMixin, {
    onEventCallBack: (...args: any[]) => void;
}, string, import("vue").VNodeProps & import("vue").AllowedComponentProps & import("vue").ComponentCustomProps, Readonly<import("vue").ExtractPropTypes<__VLS_WithDefaults<__VLS_TypePropsToRuntimeProps<MtPreviewProps>, {
    canDrag: boolean;
    canZoom: boolean;
    showPopover: boolean;
}>>> & {
    onOnEventCallBack?: ((...args: any[]) => any) | undefined;
}, {
    showPopover: boolean;
    canZoom: boolean;
    canDrag: boolean;
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
