import {defineConfig} from 'vite';
export default defineConfig({define:{'process.env.NODE_ENV':JSON.stringify('production')},build:{outDir:'../res/workspace',emptyOutDir:true,lib:{entry:'src/main.tsx',name:'FusanheWorkspace',formats:['iife'],fileName:()=> 'workspace.js'},cssCodeSplit:false,rollupOptions:{output:{assetFileNames:'workspace.[ext]'}}}});
