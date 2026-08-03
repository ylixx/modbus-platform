import { resolve } from 'path'
import { loadEnv } from 'vite'
import type { UserConfig, ConfigEnv } from 'vite'
import http from 'http'
import net from 'net'
import Vue from '@vitejs/plugin-vue'
import VueJsx from '@vitejs/plugin-vue-jsx'
import progress from 'vite-plugin-progress'
import EslintPlugin from 'vite-plugin-eslint'
import { ViteEjsPlugin } from 'vite-plugin-ejs'
import { viteMockServe } from 'vite-plugin-mock'
import ServerUrlCopy from 'vite-plugin-url-copy'
import VueI18nPlugin from '@intlify/unplugin-vue-i18n/vite'
import { createSvgIconsPlugin } from 'vite-plugin-svg-icons'
import { createStyleImportPlugin, ElementPlusResolve } from 'vite-plugin-style-import'
import UnoCSS from 'unocss/vite'
import { visualizer } from 'rollup-plugin-visualizer'

// https://vitejs.dev/config/
const root = process.cwd()

function pathResolve(dir: string) {
  return resolve(root, '.', dir)
}

export default ({ command, mode }: ConfigEnv): UserConfig => {
  // 清除系统 HTTP 代理，避免 Vite dev server 代理请求走代理导致超时
  // Node.js 的 http.request 会自动读取 http_proxy 环境变量
  const proxyKeys = ['http_proxy', 'HTTP_PROXY', 'https_proxy', 'HTTPS_PROXY', 'no_proxy', 'NO_PROXY']
  for (const k of proxyKeys) {
    if (process.env[k]) {
      console.log(`[vite-config] Clearing proxy env: ${k}=${process.env[k]}`)
      delete process.env[k]
    }
  }
  let env = {} as any
  const isBuild = command === 'build'
  if (!isBuild) {
    const modeArgIdx = process.argv.indexOf('--mode')
    const modeValue = modeArgIdx !== -1 ? process.argv[modeArgIdx + 1] : process.argv[3]
    env = loadEnv(modeValue && !modeValue.startsWith('--') ? modeValue : 'base', root)
  } else {
    env = loadEnv(mode, root)
  }
  return {
    base: env.VITE_BASE_PATH,
    plugins: [
      // HTTP API + WebSocket 手动代理插件 — 绕过 http-proxy 走系统代理的问题
      {
        name: 'manual-api-proxy',
        configureServer(server) {
          const backendUrl = new URL(env.VITE_API_BASE_URL || 'http://127.0.0.1:8000')
          const backendHost = backendUrl.hostname
          const backendPort = parseInt(backendUrl.port) || 8000

          // HTTP API 代理
          server.middlewares.use('/api/v1', (req, res, next) => {
            const path = '/api/v1' + req.url
            const options = {
              hostname: backendHost,
              port: backendPort,
              path: path,
              method: req.method,
              headers: { ...req.headers, host: `${backendHost}:${backendPort}` }
            }
            const proxyReq = http.request(options, (proxyRes) => {
              res.writeHead(proxyRes.statusCode!, proxyRes.headers as any)
              proxyRes.pipe(res, { end: true })
            })
            proxyReq.on('error', (e) => {
              console.error('[manual-proxy] Error:', e.message)
              if (!res.headersSent) res.writeHead(502)
              res.end('Bad Gateway: ' + e.message)
            })
            req.pipe(proxyReq, { end: true })
          })

          // WebSocket 代理 — 用 polka/ws 的方式直接 pipe
          server.httpServer?.on('upgrade', (req, socket, head) => {
            if (!req.url?.startsWith('/api/v1/ws')) return
            const wsUrl = new URL(req.url, `ws://${backendHost}:${backendPort}`)
            const client = net.connect(backendPort, backendHost, () => {
              const headers = [
                `GET ${req.url} HTTP/1.1`,
                `Host: ${backendHost}:${backendPort}`,
                `Upgrade: websocket`,
                `Connection: Upgrade`,
                `Sec-WebSocket-Key: ${req.headers['sec-websocket-key']}`,
                `Sec-WebSocket-Version: ${req.headers['sec-websocket-version']}`,
                ``,
                ``
              ]
              client.write(headers.join('\r\n'))
              // 写入剩余的 head 数据
              if (head.length > 0) client.write(head)
            })
            socket.pipe(client)
            client.pipe(socket)
            socket.on('error', () => client.destroy())
            client.on('error', () => socket.destroy())
          })
        }
      },
      Vue({
        script: {
          // 开启defineModel
          defineModel: true
        }
      }),
      VueJsx(),
      ServerUrlCopy(),
      progress(),
      env.VITE_USE_ALL_ELEMENT_PLUS_STYLE === 'false'
        ? createStyleImportPlugin({
            resolves: [ElementPlusResolve()],
            libs: [
              {
                libraryName: 'element-plus',
                esModule: true,
                resolveStyle: (name) => {
                  if (name === 'click-outside') {
                    return ''
                  }
                  return `element-plus/es/components/${name.replace(/^el-/, '')}/style/css`
                }
              }
            ]
          })
        : undefined,
      EslintPlugin({
        cache: false,
        failOnWarning: false,
        failOnError: false,
        include: ['src/**/*.vue', 'src/**/*.ts', 'src/**/*.tsx'] // 检查的文件
      }),
      VueI18nPlugin({
        runtimeOnly: true,
        compositionOnly: true,
        include: [resolve(__dirname, 'src/locales/**')]
      }),
      createSvgIconsPlugin({
        iconDirs: [pathResolve('src/assets/svgs')],
        symbolId: 'icon-[dir]-[name]',
        svgoOptions: true
      }),
      env.VITE_USE_MOCK === 'true'
        ? viteMockServe({
            ignore: /^\_/,
            mockPath: 'mock',
            localEnabled: !isBuild,
            prodEnabled: isBuild,
            injectCode: `
          import { setupProdMockServer } from '../mock/_createProductionServer'

          setupProdMockServer()
          `
          })
        : undefined,
      ViteEjsPlugin({
        title: env.VITE_APP_TITLE
      }),
      UnoCSS()
    ],

    css: {
      preprocessorOptions: {
        less: {
          additionalData: '@import "./src/styles/variables.module.less";',
          javascriptEnabled: true
        }
      }
    },
    resolve: {
      extensions: ['.mjs', '.js', '.ts', '.jsx', '.tsx', '.json', '.less', '.css'],
      alias: [
        {
          find: 'vue-i18n',
          replacement: 'vue-i18n/dist/vue-i18n.cjs.js'
        },
        {
          find: /\@\//,
          replacement: `${pathResolve('src')}/`
        }
      ]
    },
    esbuild: {
      pure: env.VITE_DROP_CONSOLE === 'true' ? ['console.log'] : undefined,
      drop: env.VITE_DROP_DEBUGGER === 'true' ? ['debugger'] : undefined
    },
    build: {
      target: 'es2015',
      outDir: env.VITE_OUT_DIR || 'dist',
      sourcemap: env.VITE_SOURCEMAP === 'true',
      // brotliSize: false,
      rollupOptions: {
        plugins: env.VITE_USE_BUNDLE_ANALYZER === 'true' ? [visualizer()] : undefined,
        // 拆包
        output: {
          manualChunks: {
            'vue-chunks': ['vue', 'vue-router', 'pinia', 'vue-i18n'],
            'element-plus': ['element-plus'],
            'wang-editor': ['@wangeditor/editor', '@wangeditor/editor-for-vue'],
            echarts: ['echarts', 'echarts-wordcloud']
          }
        }
      },
      cssCodeSplit: !(env.VITE_USE_CSS_SPLIT === 'false'),
      cssTarget: ['chrome31']
    },
    server: {
      port: 3001,
      // 不使用 Vite 内置 proxy（会走系统代理报错），改用 manual-api-proxy 插件
      proxy: {
        '/api/v1/ws': {
          target: env.VITE_API_BASE_URL,
          changeOrigin: true,
          ws: true,
          agent: new http.Agent({ keepAlive: false })
        }
      },
      hmr: {
        overlay: false
      },
      host: '0.0.0.0'
    },
    optimizeDeps: {
      include: [
        'vue',
        'vue-router',
        'vue-types',
        'element-plus/es/locale/lang/zh-cn',
        'element-plus/es/locale/lang/en',
        '@iconify/iconify',
        '@iconify/vue',
        '@vueuse/core',
        'axios',
        'qs',
        'echarts',
        'echarts-wordcloud',
        'qrcode',
        '@wangeditor/editor',
        '@wangeditor/editor-for-vue',
        'vue-json-pretty',
        '@zxcvbn-ts/core',
        'dayjs',
        'cropperjs'
      ]
    }
  }
}
