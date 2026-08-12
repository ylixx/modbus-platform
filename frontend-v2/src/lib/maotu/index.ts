/**
 * maotu 组态引擎库（LGPL-3.0，作为库链接使用）
 * 构建产物来自 maotu-webtopo v0.3.1 (https://github.com/yaolunmao/maotu-webtopo)
 * 样式只在进入组态编辑/运行页面时加载，避免全局污染
 */
import { MtEdit, MtPreview, leftAsideStore } from '@/lib/maotu/maotu.es.js'
import './style.css'

export { MtEdit, MtPreview, leftAsideStore }