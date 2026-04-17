export const ROUTES = {
  login: "/login",
  home: "/home",
  detail: (id: string) => `/home/details/${id}`,
  detailPattern: "/home/details/:id",
} as const;
