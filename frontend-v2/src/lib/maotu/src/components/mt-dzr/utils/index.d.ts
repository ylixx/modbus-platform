import type { IDzrPropsModelValue } from '../types';
import type { MouseTouchEvent } from './types';
/**
 * 会自动销毁的鼠标移动事件
 * @param onMousemove
 */
export declare const autoDestroyMouseMove: (onMousemove: (e: MouseTouchEvent) => void, mouseUpCallBack?: () => void) => void;
/**
 * 根据坐标对齐到网格
 * @param position 当前坐标
 * @param grid 网格大小
 * @returns 对应网格的坐标
 */
export declare const alignToGrid: (position: number, grid?: number) => number;
/** 根据移动的距离对齐到网格
 * @param diff 移动的距离
 * @param grid 网格大小
 */
export declare const calcGrid: (diff: number, grid?: number) => number;
/**
 * 获取当前点击坐标 根据pc端和移动端获取
 * @param e
 * @returns
 */
export declare function getXY(e: MouseTouchEvent): {
    clientX: number;
    clientY: number;
};
export declare const getLength: (x: number, y: number) => number;
export declare const degToRadian: (deg: number) => number;
/**
 * 计算并返回给定类型变换的新样式。
 *
 * @param {string} type - 变换的类型。
 * @param {any} rect - 矩形对象。
 * @param {number} deltaW - 宽度变化。
 * @param {number} deltaH - 高度变化。
 * @param {number | undefined} ratio - 比例。
 * @param {number} minWidth - 最小宽度。
 * @param {number} minHeight - 最小高度。
 * @returns {Object} 矩形的新位置和大小。
 */
export declare const getNewStyle: (type: string, rect: any, deltaW: number, deltaH: number, ratio: number | undefined, minWidth: number, minHeight: number) => {
    position: {
        centerX: any;
        centerY: any;
    };
    size: {
        width: number;
        height: number;
    };
};
/**
 * 根据矩形的中心坐标、尺寸和角度计算左上角的位置。
 *
 * @param {object} params - 计算的参数。
 * @param {number} params.centerX - 矩形的中心点的 x 坐标。
 * @param {number} params.centerY - 矩形的中心点的 y 坐标。
 * @param {number} params.width - 矩形的宽度。
 * @param {number} params.height - 矩形的高度。
 * @param {number} params.angle - 矩形的旋转角度。
 * @return {object} - 矩形的左上角位置。
 */
export declare const centerToTL: ({ centerX, centerY, width, height, angle }: any) => IDzrPropsModelValue;
/**
 * 格式化数据并返回一个包含更新后尺寸和位置的对象。
 *
 * @param {IDzrPropsModelValue} data - 包含宽度和高度的数据。
 * @param {number} centerX - 中心点的x坐标。
 * @param {number} centerY - 中心点的y坐标。
 * @return {object} - 一个包含更新后尺寸和位置的对象。
 */
export declare const formatData: (data: IDzrPropsModelValue, centerX: number, centerY: number) => {
    width: number;
    height: number;
    left: number;
    top: number;
};
/**
 * 生成随机字符串
 * @param len 生成个数
 */
export declare const randomString: (len?: number) => string;
