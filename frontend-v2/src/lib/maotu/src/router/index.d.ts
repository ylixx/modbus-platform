export declare const constantRoutes: ({
    path: string;
    component: () => Promise<typeof import("../views/edit/index.vue")>;
    name?: undefined;
} | {
    name: string;
    path: string;
    component: () => Promise<typeof import("../views/edit/index.vue")>;
})[];
declare const router: import("vue-router").Router;
export default router;
