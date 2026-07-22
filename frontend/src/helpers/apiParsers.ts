import {
  AlbumDetailAPIInterface,
  AlbumDetailInterface,
  AlbumListItemAPIInterface,
  AlbumListItemInterface,
  MediaAPIInterface,
  MediaInterface,
  ShareLinkAPIInterface,
  ShareLinkInterface,
} from "./interfaces";

export function parseMedia(media: MediaAPIInterface): MediaInterface {
  return {
    id: media.id,
    album: media.album,
    type: media.type,
    originalFilename: media.original_filename,
    storageKey: media.storage_key,
    thumbnailKey: media.thumbnail_key,
    thumbnailUrl: media.thumbnail_url,
    fileUrl: media.file_url,
    size: media.size,
    contentType: media.content_type,
    width: media.width,
    height: media.height,
    duration: media.duration,
    takenAt: media.taken_at,
    order: media.order,
    processingStatus: media.processing_status,
    createdAt: media.created_at,
  };
}

export function parseAlbumListItem(album: AlbumListItemAPIInterface): AlbumListItemInterface {
  return {
    id: album.id,
    name: album.name,
    slug: album.slug,
    startDate: album.start_date,
    endDate: album.end_date,
    mediaCount: album.media_count,
    coverThumbnailUrl: album.cover_thumbnail_url,
    createdAt: album.created_at,
  };
}

export function parseAlbumDetail(album: AlbumDetailAPIInterface): AlbumDetailInterface {
  return {
    id: album.id,
    name: album.name,
    slug: album.slug,
    description: album.description,
    startDate: album.start_date,
    endDate: album.end_date,
    cover: album.cover,
    media: album.media.map(parseMedia),
    createdAt: album.created_at,
    updatedAt: album.updated_at,
  };
}

export function parseShareLink(shareLink: ShareLinkAPIInterface): ShareLinkInterface {
  return {
    id: shareLink.id,
    album: shareLink.album,
    token: shareLink.token,
    expiresAt: shareLink.expires_at,
    isActive: shareLink.is_active,
    createdAt: shareLink.created_at,
    url: shareLink.url,
  };
}
