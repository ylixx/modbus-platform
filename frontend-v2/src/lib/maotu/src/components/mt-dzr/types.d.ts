export interface IDzrProps {
    id: string;
    modelValue: IDzrPropsModelValue;
    scaleRatio?: number;
    hide: boolean;
    grid?: IDzrPropsGrid;
    resize?: boolean;
    rotate?: boolean;
    lock?: boolean;
    active?: boolean;
    useProportionalScaling?: boolean;
    showGhostDom?: boolean;
    class?: string;
    disabled: boolean;
    adsorp_diff?: {
        x: number;
        y: number;
    };
}
export interface IDzrPropsModelValue {
    left: number;
    top: number;
    width: number;
    height: number;
    angle: number;
}
export interface IDzrPropsGrid {
    enabled: boolean;
    align: boolean;
    size: number;
}
