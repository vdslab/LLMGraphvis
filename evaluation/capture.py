from __future__ import annotations

from pathlib import Path
from typing import Any

from .config import EvaluationConfig


async def capture_graph(
    config: EvaluationConfig,
    chat_id: int,
    access_token: str,
    expected_nodes: int,
    expected_links: int,
    output_path: Path,
) -> dict[str, Any]:
    try:
        from playwright.async_api import async_playwright
    except ImportError:
        return {
            "captured": False,
            "path": None,
            "errors": ["Playwright is not installed. Run scripts/setup-evaluation."],
        }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    console_errors: list[str] = []
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(headless=True)
        context = await browser.new_context(viewport={"width": 1440, "height": 900})
        await context.add_cookies(
            [
                {
                    "name": "access_token",
                    "value": f"Bearer {access_token}",
                    "url": config.frontend_url,
                    "httpOnly": True,
                    "sameSite": "Lax",
                }
            ]
        )
        page = await context.new_page()
        page.on(
            "console",
            lambda message: (
                console_errors.append(message.text) if message.type == "error" else None
            ),
        )
        page.on("pageerror", lambda error: console_errors.append(str(error)))

        try:
            await page.goto(
                f"{config.frontend_url}/chat/{chat_id}",
                wait_until="domcontentloaded",
                timeout=60_000,
            )
            graph = page.get_by_test_id("network-graph")
            await graph.wait_for(state="visible", timeout=60_000)
            if expected_nodes:
                count_expression = (
                    "([selector, count]) => "
                    "document.querySelectorAll(selector).length === count"
                )
                await page.wait_for_function(
                    count_expression,
                    arg=["[data-testid='network-graph'] svg circle", expected_nodes],
                    timeout=60_000,
                )
            await graph.screenshot(path=str(output_path))
            node_elements = await graph.locator("svg circle").count()
            link_elements = await graph.locator("svg line").count()
            label_elements = await graph.locator("svg text").count()
            svg_validation = await graph.locator("svg").evaluate(
                """svg => {
                    const finite = value => Number.isFinite(Number(value));
                    const nodeGroups = [
                      ...svg.querySelectorAll('g[transform^="translate"]')
                    ];
                    const badNodes = nodeGroups
                      .filter(group => {
                        const transform = group.getAttribute('transform') || '';
                        const values = transform.match(/-?\\d+(?:\\.\\d+)?/g) || [];
                        const circle = group.querySelector('circle');
                        return values.length < 2 || values.some(v => !finite(v)) ||
                          !circle || !finite(circle.getAttribute('r')) ||
                          Number(circle.getAttribute('r')) <= 0 ||
                          !CSS.supports('color', circle.getAttribute('fill') || '');
                      }).length;
                    const badLinks = [...svg.querySelectorAll('line')].filter(line => {
                      const numeric = ['x1', 'y1', 'x2', 'y2', 'stroke-width'];
                      return numeric.some(name => !finite(line.getAttribute(name))) ||
                        !CSS.supports('color', line.getAttribute('stroke') || '');
                    }).length;
                    return {
                      invalid_node_elements: badNodes,
                      invalid_link_elements: badLinks
                    };
                }"""
            )
            result = {
                "captured": True,
                "path": str(output_path),
                "node_elements": node_elements,
                "link_elements": link_elements,
                "label_elements": label_elements,
                "expected_nodes": expected_nodes,
                "expected_links": expected_links,
                "dom_consistent": (
                    node_elements == expected_nodes and link_elements == expected_links
                ),
                "svg_validation": svg_validation,
                "errors": console_errors[-20:],
            }
        except Exception as exc:
            result = {
                "captured": False,
                "path": None,
                "errors": console_errors[-20:] + [f"{type(exc).__name__}: {exc}"],
            }
        finally:
            await context.close()
            await browser.close()
    return result
