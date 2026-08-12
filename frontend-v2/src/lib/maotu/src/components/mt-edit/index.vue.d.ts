import type { IExportJson } from './components/types';
type MtEditProps = {
    useThumbnail?: boolean;
};
declare const _default: __VLS_WithTemplateSlots<import("vue").DefineComponent<__VLS_WithDefaults<__VLS_TypePropsToRuntimeProps<MtEditProps>, {
    useThumbnail: boolean;
}>, {
    setImportJson: (exportJson: IExportJson) => boolean;
}, unknown, {}, {}, import("vue").ComponentOptionsMixin, import("vue").ComponentOptionsMixin, {
    onPreviewClick: (...args: any[]) => void;
    onReturnClick: (...args: any[]) => void;
    onSaveClick: (...args: any[]) => void;
    onThumbnailClick: (...args: any[]) => void;
}, string, import("vue").VNodeProps & import("vue").AllowedComponentProps & import("vue").ComponentCustomProps, Readonly<import("vue").ExtractPropTypes<__VLS_WithDefaults<__VLS_TypePropsToRuntimeProps<MtEditProps>, {
    useThumbnail: boolean;
}>>> & {
    onOnPreviewClick?: ((...args: any[]) => any) | undefined;
    onOnReturnClick?: ((...args: any[]) => any) | undefined;
    onOnSaveClick?: ((...args: any[]) => any) | undefined;
    onOnThumbnailClick?: ((...args: any[]) => any) | undefined;
}, {
    useThumbnail: boolean;
}, {}>, {
    deviceBind?(_: {
        item: import("./store/types").IDoneJson;
    }): any;
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
