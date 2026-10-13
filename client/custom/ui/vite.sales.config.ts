import {defineConfig} from 'vite';
export default defineConfig({define:{'process.env.NODE_ENV':JSON.stringify('production')},build:{outDir:'../res/sales',emptyOutDir:true,lib:{entry:'src/sales.tsx',name:'FusanheSales',formats:['iife'],fileName:()=> 'sales.js',cssFileName:'style'},cssCodeSplit:false}});
