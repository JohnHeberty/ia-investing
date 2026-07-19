import { NextRequest } from "next/server";
import { afterEach, describe, expect, it } from "vitest";

import { proxy } from "./proxy";

const previousEnvironment = process.env.NEXT_PUBLIC_APP_ENV;

afterEach(() => {
  process.env.NEXT_PUBLIC_APP_ENV = previousEnvironment;
});

describe("protected route proxy", () => {
  it("redirects an unauthenticated production request to login", () => {
    process.env.NEXT_PUBLIC_APP_ENV = "production";
    const response = proxy(new NextRequest("https://investing.example/portfolios/1"));
    expect(response.status).toBe(307);
    expect(response.headers.get("location")).toBe(
      "https://investing.example/login?return_to=%2Fportfolios%2F1",
    );
  });

  it("allows public login and an authenticated route", () => {
    process.env.NEXT_PUBLIC_APP_ENV = "production";
    expect(
      proxy(new NextRequest("https://investing.example/login")).headers.get("x-middleware-next"),
    ).toBe("1");
    const request = new NextRequest("https://investing.example/portfolios/1", {
      headers: { cookie: "ia_session=authenticated" },
    });
    expect(proxy(request).headers.get("x-middleware-next")).toBe("1");
  });
});
