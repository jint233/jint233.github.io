#!/usr/bin/env python3
import argparse
import errno
import re
import sys
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit


class PreviewHandler(SimpleHTTPRequestHandler):
    def do_GET(self) -> None:
        if urlsplit(self.path).path == "/sitemap.xml":
            self.serve_local_sitemap()
            return
        super().do_GET()

    def serve_local_sitemap(self) -> None:
        sitemap_path = Path(self.directory) / "sitemap.xml"
        if not sitemap_path.is_file():
            self.send_error(404, "File not found")
            return

        host = self.headers.get("Host", f"{self.server.server_name}:{self.server.server_port}")
        origin = f"http://{host}"
        content = sitemap_path.read_text(encoding="utf-8")
        content = re.sub(r"(<loc>)https?://[^/]+", rf"\g<1>{origin}", content)
        payload = content.encode("utf-8")

        self.send_response(200)
        self.send_header("Content-Type", "application/xml; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)


def main() -> None:
    parser = argparse.ArgumentParser(description="Serve the built documentation locally")
    parser.add_argument("--bind", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--directory", default="site")
    args = parser.parse_args()

    handler = partial(PreviewHandler, directory=args.directory)
    try:
        server = ThreadingHTTPServer((args.bind, args.port), handler)
    except OSError as error:
        if error.errno == errno.EADDRINUSE:
            print(
                f"端口 {args.port} 已被占用，请先停止原预览进程，"
                f"或使用 make serve PORT=<其他端口>",
                file=sys.stderr,
            )
            raise SystemExit(2) from None
        raise
    print(f"Serving HTTP on http://{args.bind}:{args.port}/")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
