declare const _default: import("vue").DefineComponent<{
    contentObj: {
        type: ObjectConstructor;
        default: () => void;
    };
}, {}, unknown, {}, {}, import("vue").ComponentOptionsMixin, import("vue").ComponentOptionsMixin, {
    "update:contentObj": (...args: any[]) => void;
}, string, import("vue").VNodeProps & import("vue").AllowedComponentProps & import("vue").ComponentCustomProps, Readonly<import("vue").ExtractPropTypes<{
    contentObj: {
        type: ObjectConstructor;
        default: () => void;
    };
}>> & {
    "onUpdate:contentObj"?: ((...args: any[]) => any) | undefined;
}, {
    contentObj: Record<string, any>;
}, {}>;
export default _default;
