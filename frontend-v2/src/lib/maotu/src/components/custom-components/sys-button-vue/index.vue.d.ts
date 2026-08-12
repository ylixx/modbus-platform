import type { PropType } from 'vue';
type ButtonType = '' | 'default' | 'success' | 'warning' | 'info' | 'primary' | 'danger';
declare const _default: import("vue").DefineComponent<{
    text: {
        type: StringConstructor;
        default: string;
    };
    type: {
        type: PropType<ButtonType>;
        default: string;
    };
    round: {
        type: BooleanConstructor;
        default: boolean;
    };
}, {}, unknown, {}, {}, import("vue").ComponentOptionsMixin, import("vue").ComponentOptionsMixin, {}, string, import("vue").VNodeProps & import("vue").AllowedComponentProps & import("vue").ComponentCustomProps, Readonly<import("vue").ExtractPropTypes<{
    text: {
        type: StringConstructor;
        default: string;
    };
    type: {
        type: PropType<ButtonType>;
        default: string;
    };
    round: {
        type: BooleanConstructor;
        default: boolean;
    };
}>>, {
    type: ButtonType;
    text: string;
    round: boolean;
}, {}>;
export default _default;
