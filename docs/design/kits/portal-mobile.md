# Portal mobile kit (T7-M) and the TPL-19 specimen: hand-off to R-03 and every POR screen at 390

F-06-T23 (from F-06-T10). The 390 × 844 portal-mobile frame (56 firm header, 64 tab bar, More
sheet) and the mobile home cards are locked for R-03's POR-19 and every POR screen at 390. The
portal never renders "Accrued" or blue (DEC-01).

Code: `packages/ui/src/templates/portal-layout.tsx` (`PortalLayout`, `portalNav`, mobile variant),
`portal-mobile-home.tsx` (`MobileGreeting`, `ReturnProgressCard`, `MobileTodoCard`,
`MobileTeamCard`). Specimens: TPL-19 frames 1, 2, 5, 6, 7, 9 (`tpl19.test.tsx`).

## Props

| Kit | Props | From |
|---|---|---|
| `ReturnProgressCard` | the return's stage and dates | the portal home read (counts and stages are the server's) |
| `MobileTodoCard` | `MobileTodo[]` | the portal's open requests (match TPL-07) |
| `MobileTeamCard` | `TeamMember[]` | the engagement team's portal-visible members |
| Sign at 390 | `SigningCeremony` with `layout: "phone"`, `stickyBarHeight: 64` | see `signing.md` |

## Deferred (DEC-97)

TPL-19 frames 3 (camera page 1), 4 (camera page 2, "Done — 2 pages") and 8 (blur warning), and the
caption-only camera-permission-off variant, are deferred to R-03's S59–S63 window
(`docs/plan/deferrals/R-03-tpl19.md`); the gallery shows a Deferred (DEC-97) placeholder for each.
v1 capture is the native file input with `capture` and server-side stitching (DEC-45).
