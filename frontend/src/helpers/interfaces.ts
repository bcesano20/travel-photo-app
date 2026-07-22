export interface AuthLoginInterface {
  email: string;
  password: string;
}

export interface APIErrorInterface {
  status: number;
  message: string;
}

export type MediaType = "photo" | "video";
export type ProcessingStatus = "pending" | "ready" | "error";

export interface MediaAPIInterface {
  id: number;
  album: number;
  type: MediaType;
  original_filename: string;
  storage_key: string;
  thumbnail_key: string;
  thumbnail_url: string | null;
  file_url: string;
  size: number;
  content_type: string;
  width: number | null;
  height: number | null;
  duration: number | null;
  taken_at: string | null;
  order: number;
  processing_status: ProcessingStatus;
  created_at: string;
}

export interface MediaInterface {
  id: number;
  album: number;
  type: MediaType;
  originalFilename: string;
  storageKey: string;
  thumbnailKey: string;
  thumbnailUrl: string | null;
  fileUrl: string;
  size: number;
  contentType: string;
  width: number | null;
  height: number | null;
  duration: number | null;
  takenAt: string | null;
  order: number;
  processingStatus: ProcessingStatus;
  createdAt: string;
}

export interface AlbumListItemAPIInterface {
  id: number;
  name: string;
  slug: string;
  start_date: string | null;
  end_date: string | null;
  media_count: number;
  cover_thumbnail_url: string | null;
  created_at: string;
}

export interface AlbumListItemInterface {
  id: number;
  name: string;
  slug: string;
  startDate: string | null;
  endDate: string | null;
  mediaCount: number;
  coverThumbnailUrl: string | null;
  createdAt: string;
}

export interface AlbumDetailAPIInterface {
  id: number;
  name: string;
  slug: string;
  description: string;
  start_date: string | null;
  end_date: string | null;
  cover: number | null;
  media: MediaAPIInterface[];
  created_at: string;
  updated_at: string;
}

export interface AlbumDetailInterface {
  id: number;
  name: string;
  slug: string;
  description: string;
  startDate: string | null;
  endDate: string | null;
  cover: number | null;
  media: MediaInterface[];
  createdAt: string;
  updatedAt: string;
}

export interface ShareLinkAPIInterface {
  id: number;
  album: number;
  token: string;
  expires_at: string | null;
  is_active: boolean;
  created_at: string;
  url: string;
}

export interface ShareLinkInterface {
  id: number;
  album: number;
  token: string;
  expiresAt: string | null;
  isActive: boolean;
  createdAt: string;
  url: string;
}

export interface AlbumDataInterface {
  name: string;
  description: string;
  startDate: string;
  endDate: string;
}
