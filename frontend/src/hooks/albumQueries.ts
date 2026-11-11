import { QueryClient, useQuery } from "@tanstack/react-query";

import { API_ENDPOINT_URL, PENDING_MEDIA_POLL_INTERVAL_MS } from "@/helpers/constants";
import {
  AlbumAdminDetailAPIInterface,
  AlbumListItemAPIInterface,
  ShareLinkAPIInterface,
} from "@/helpers/interfaces";
import { parseAlbumAdminDetail, parseAlbumListItem, parseShareLink } from "@/helpers/apiParsers";
import { apiGet } from "@/helpers/apiHelper";

// Every album-related query lives under the "albums" prefix, so after any
// change (create, edit, delete, upload) one invalidation of `albumKeys.all`
// refreshes the list, every detail and every share link.
export const albumKeys = {
  all: ["albums"] as const,
  list: () => [...albumKeys.all, "list"] as const,
  detail: (albumId: string | number) => [...albumKeys.all, "detail", String(albumId)] as const,
  shareLink: (albumId: string | number) =>
    [...albumKeys.all, "share-link", String(albumId)] as const,
};

export const fetchAlbumList = async () => {
  const data = await apiGet<AlbumListItemAPIInterface[]>(API_ENDPOINT_URL.ALBUMS_API);
  return data.map(parseAlbumListItem);
};

export const fetchAlbumDetail = async (albumId: string | number) => {
  const data = await apiGet<AlbumAdminDetailAPIInterface>(
    `${API_ENDPOINT_URL.ALBUMS_API}${albumId}/`,
  );
  return parseAlbumAdminDetail(data);
};

// The active (non-revoked) share link of an album, or null if it has none.
export const fetchActiveShareLink = async (albumId: string | number) => {
  const links = await apiGet<ShareLinkAPIInterface[]>(
    `${API_ENDPOINT_URL.SHARE_LINKS_API}?album=${albumId}`,
  );
  return links.map(parseShareLink).find((link) => link.isActive) ?? null;
};

export const useAlbumList = () => useQuery({ queryKey: albumKeys.list(), queryFn: fetchAlbumList });

export const useAlbumDetail = (albumId: string | number) =>
  useQuery({
    queryKey: albumKeys.detail(albumId),
    queryFn: () => fetchAlbumDetail(albumId),
    // While any file is still being processed by the worker, poll so its
    // thumbnail shows up on its own. Polling stops once nothing is pending.
    refetchInterval: (query) =>
      query.state.data?.media.some((item) => item.processingStatus === "pending")
        ? PENDING_MEDIA_POLL_INTERVAL_MS
        : false,
  });

export const useActiveShareLink = (albumId: string | number) =>
  useQuery({
    queryKey: albumKeys.shareLink(albumId),
    queryFn: () => fetchActiveShareLink(albumId),
  });

// Reads an album through the cache: returns the cached data while it is fresh
// and fetches otherwise. Replaces the deprecated queryClient.fetchQuery.
export const queryAlbumDetail = (queryClient: QueryClient, albumId: string | number) =>
  queryClient.query({
    queryKey: albumKeys.detail(albumId),
    queryFn: () => fetchAlbumDetail(albumId),
  });

// Warms the cache (e.g. on hover) so opening an album feels instant. It only fetches if the album isn't cached or its cache is stale.
// queryClient.query() rejects on failure, so the error is swallowed here: a failed prefetch is harmless, the page fetches the album on its own when opened.
export const prefetchAlbumDetail = async (
  queryClient: QueryClient,
  albumId: string | number,
): Promise<void> => {
  try {
    await queryAlbumDetail(queryClient, albumId);
  } catch {
    // Intentionally ignored, see above.
  }
};
