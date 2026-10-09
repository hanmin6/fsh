# 福三和品牌资源

来源页面：https://www.gzfusanhesp.com/en ，获取日期：2026-09-18。

- `logo-full.png`：https://www.gzfusanhesp.com/brand/fusanhe-logo.png 。官网原始红色皇冠 Logo，保持原图、颜色与比例；登录和导航使用，不重绘、不裁切。
- `favicon-crown-64.png` / `favicon-crown.ico`：从上述原图提取皇冠，用于浏览器标签页；保持皇冠颜色与比例，透明方形画布，ICO 包含 16–128px 尺寸。原始 Logo 保持不变。
- `branding.css`：隐藏 CRM 登录页和工作台底部的 EspoCRM 署名；通过自定义客户端元数据加载，不修改上游核心文件。
- `login-factory.webp`：https://www.gzfusanhesp.com/media/factory-fusanhe-factory-960.webp 。官网标注的广州工厂实拍，原始 960×540 WebP，用于桌面登录辅助背景；未转换，窄屏隐藏。
- `brand.css`：官网计算样式提取：foreground #20251f、primary #c83a28、background #f7f5ef、border #dcd8ce。金色采用官网视觉中的低饱和方向 #c7a36a；状态色为办公可读性调整。

官网特点：红色 Logo 置白底，Arial/Helvetica 无衬线，方角按钮，细描边标签，工业生产实拍；桌面大留白和大标题，窄屏折叠导航。CRM 保留品牌识别，改用系统中文字体、6px 圆角、34px 控件、40px 行高、12–20px 字级、8px 基准间距。无远程字体或图片运行依赖。

## 维护与验收

完整扩展说明、复现命令、测试结果、响应式行为及已知限制见 [FRONTEND.md](FRONTEND.md)。

测试命令（项目根目录）：

```sh
node --test client/custom/tests/frontend.test.cjs
python3 -m unittest discover -s tests -v
make check
docker compose exec -T espocrm bin/command rebuild
```

运行时配置与 `.env` 必须保持一致。首次升级或长时间开发后请完整刷新浏览器，避免旧 AMD 模块与新视图混用。品牌图像合计约 192 KB，无需额外 npm 运行依赖。
