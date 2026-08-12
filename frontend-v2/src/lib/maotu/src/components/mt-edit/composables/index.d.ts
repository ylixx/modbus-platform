import type { IExportJson } from '../components/types';
import type { IDoneJson, IGlobalStoreCanvasCfg, IGlobalStoreGridCfg } from '../store/types';
export declare const genExportJson: (canvasCfg: IGlobalStoreCanvasCfg, gridCfg: IGlobalStoreGridCfg, doneJson: IDoneJson[]) => {
    exportJson: IExportJson;
};
export declare const useExportJsonToDoneJson: (json: IExportJson) => {
    canvasCfg: IGlobalStoreCanvasCfg;
    gridCfg: IGlobalStoreGridCfg;
    importDoneJson: IDoneJson[];
};
