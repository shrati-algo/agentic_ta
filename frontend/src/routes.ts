export const ROUTES = {
  home: "/home",
  detail: (id: string) => `/home/details/${id}`,
  detailPattern: "/home/details/:id",
} as const;
