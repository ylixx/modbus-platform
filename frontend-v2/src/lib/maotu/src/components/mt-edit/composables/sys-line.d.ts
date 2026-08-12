import type { IDoneJson, IDoneJsonBinfo } from '../store/types';
/**
 * 更新系统连线实际宽高
 * @param sys_lines
 * @param scale
 */
export declare const useUpdateSysLineRect: (sys_lines: IDoneJson[], canvasDom: HTMLElement, scale: number) => void;
/**
 * 更新系统连线
 * @param sys_lines 要更新的连线列表
 * @param done_json 所有组件信息
 * @param canvasDom 画布dom
 * @param scale 画布缩放
 */
export declare const useUpdateSysLine: (sys_lines: IDoneJson[], done_json: IDoneJson[], canvasDom: HTMLElement, scale: number, move_binfo?: IDoneJsonBinfo & {
    id: string;
}) => void;
