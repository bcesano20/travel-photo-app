export const ACCESS_TOKEN_KEY = "trip_gallery_access_token";
export const REFRESH_TOKEN_KEY = "trip_gallery_refresh_token";

export const API_URL = process.env.NEXT_PUBLIC_API_URL;

export const ERROR_MESSAGES = {
  INVALID_CREDENTIALS: "Invalid email or password.",
  INCORRECT_CREDENTIALS_ES: "Email o contraseña incorrectos.",
  FIELD_REQUIRED: "Este campo es obligatorio.",
  EMAIL_FORMAT_INVALID: "Ingresá un email válido.",
  ALBUMS_NOT_LOAD: "No se pudieron cargar los álbumes.",
  ALBUM_NOT_CREATED: "No se pudo crear el álbum.",
};

export const REGEXP = {
  EMAIL_REGEX: /^[^\s@]+@[^\s@]+\.[^\s@]+$/,
};

export const API_ENDPOINT_URL = {
  REFRESH: "api/auth/token/refresh/",
  ALBUMS_API: "api/albums/",
  SHARE_LINKS_API: "/api/share-links/",
  MEDIA_API: "api/media/",
  PRESIGNED_UPLOAD_API: "/api/media/presigned-upload/",
};

export const ROUTES = {
  LOGIN: "/login",
  ADMIN: "/admin",
  ALBUM: "/admin/albums",
};
