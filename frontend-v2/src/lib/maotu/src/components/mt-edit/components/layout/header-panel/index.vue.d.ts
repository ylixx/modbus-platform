import type { IRealTimeData } from '../../../../../components/mt-edit/store/types';
type HeaderPanelProps = {
    leftAside: boolean;
    rightAside: boolean;
    selectedItemsId: string[];
    groupEnabled: boolean;
    unGroupEnabled: boolean;
    alignEnabled: boolean;
    deleteEnabled: boolean;
    lockState: boolean;
    undoEnabled: boolean;
    redoEnabled: boolean;
    realTimeData: IRealTimeData;
    useThumbnail?: boolean;
};
declare const _default: import("vue").DefineComponent<__VLS_WithDefaults<__VLS_TypePropsToRuntimeProps<HeaderPanelProps>, {
    leftAside: boolean;
    rightAside: boolean;
    useThumbnail: boolean;
    selectedItemsId: () => never[];
}>, {}, unknown, {}, {}, import("vue").ComponentOptionsMixin, import("vue").ComponentOptionsMixin, {
    "update:leftAside": (...args: any[]) => void;
    "update:rightAside": (...args: any[]) => void;
    onGroupClick: (...args: any[]) => void;
    onUngroupClick: (...args: any[]) => void;
    onDeleteClick: (...args: any[]) => void;
    onExportClick: (...args: any[]) => void;
    onTreeClick: (...args: any[]) => void;
    alignSelected: (...args: any[]) => void;
    "update:lockState": (...args: any[]) => void;
    onHelpClick: (...args: any[]) => void;
    onRedoClick: (...args: any[]) => void;
    onUndoClick: (...args: any[]) => void;
    onImportClick: (...args: any[]) => void;
    onPreviewClick: (...args: any[]) => void;
    onReturnClick: (...args: any[]) => void;
    onSaveClick: (...args: any[]) => void;
    onDrawLineClick: (...args: any[]) => void;
    onThumbnailClick: (...args: any[]) => void;
}, string, import("vue").VNodeProps & import("vue").AllowedComponentProps & import("vue").ComponentCustomProps, Readonly<import("vue").ExtractPropTypes<__VLS_WithDefaults<__VLS_TypePropsToRuntimeProps<HeaderPanelProps>, {
    leftAside: boolean;
    rightAside: boolean;
    useThumbnail: boolean;
    selectedItemsId: () => never[];
}>>> & {
    "onUpdate:leftAside"?: ((...args: any[]) => any) | undefined;
    "onUpdate:rightAside"?: ((...args: any[]) => any) | undefined;
    onOnGroupClick?: ((...args: any[]) => any) | undefined;
    onOnUngroupClick?: ((...args: any[]) => any) | undefined;
    onOnDeleteClick?: ((...args: any[]) => any) | undefined;
    onOnExportClick?: ((...args: any[]) => any) | undefined;
    onOnTreeClick?: ((...args: any[]) => any) | undefined;
    onAlignSelected?: ((...args: any[]) => any) | undefined;
    "onUpdate:lockState"?: ((...args: any[]) => any) | undefined;
    onOnHelpClick?: ((...args: any[]) => any) | undefined;
    onOnRedoClick?: ((...args: any[]) => any) | undefined;
    onOnUndoClick?: ((...args: any[]) => any) | undefined;
    onOnImportClick?: ((...args: any[]) => any) | undefined;
    onOnPreviewClick?: ((...args: any[]) => any) | undefined;
    onOnReturnClick?: ((...args: any[]) => any) | undefined;
    onOnSaveClick?: ((...args: any[]) => any) | undefined;
    onOnDrawLineClick?: ((...args: any[]) => any) | undefined;
    onOnThumbnailClick?: ((...args: any[]) => any) | undefined;
}, {
    leftAside: boolean;
    rightAside: boolean;
    selectedItemsId: string[];
    useThumbnail: boolean;
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
