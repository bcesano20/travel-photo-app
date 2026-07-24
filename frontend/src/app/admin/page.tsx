"use client";

import { useEffect, useState } from "react";
import Link from "next/link";

import { API_ENDPOINT_URL, ERROR_MESSAGES, ROUTES } from "@/helpers/constants";
import {
  AlbumDataInterface,
  AlbumListItemAPIInterface,
  AlbumListItemInterface,
} from "@/helpers/interfaces";
import { parseAlbumListItem } from "@/helpers/apiParsers";
import { ApiError, apiGet, apiPost } from "@/helpers/apiHelper";
import { Button, Input, Textarea } from "@/components";

const ALBUM_DATA_DEFAULT: AlbumDataInterface = {
  name: "",
  description: "",
  startDate: "",
  endDate: "",
};

type AlbumFormErrors = Partial<Record<keyof AlbumDataInterface, string>>;

const NewAlbumForm = ({ onCreated }: { onCreated: () => void }) => {
  const [albumData, setAlbumData] = useState<AlbumDataInterface>(ALBUM_DATA_DEFAULT);
  const [formErrors, setFormErrors] = useState<AlbumFormErrors>({});

  const [loading, setLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  const handleChange = (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) => {
    const { name, value } = e.target;

    setAlbumData((prev) => ({ ...prev, [name]: value }));
    setFormErrors((prev) => ({ ...prev, [name]: undefined }));
  };

  const isValidForm = (): boolean => {
    const errors: AlbumFormErrors = {};

    if (!albumData.name) {
      errors.name = ERROR_MESSAGES.FIELD_REQUIRED;
    }

    if (albumData.startDate && albumData.endDate && albumData.endDate < albumData.startDate) {
      errors.endDate = ERROR_MESSAGES.END_DATE_BEFORE_START_DATE;
    }

    setFormErrors(errors);
    return Object.keys(errors).length === 0;
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!isValidForm()) return;

    setLoading(true);
    setError(null);
    try {
      await apiPost(API_ENDPOINT_URL.ALBUMS_API, {
        name: albumData.name,
        description: albumData.description,
        start_date: albumData.startDate || null,
        end_date: albumData.endDate || null,
      });
      onCreated();
    } catch {
      setError(ERROR_MESSAGES.ALBUM_NOT_CREATED);
    } finally {
      setLoading(false);
    }
  };

  return (
    <form
      onSubmit={handleSubmit}
      className="mb-6 rounded-xl border border-neutral-200 bg-white p-4"
    >
      <div className="mb-3">
        <Input
          name="name"
          label="Nombre"
          value={albumData.name}
          onChange={handleChange}
          placeholder="Nombre del Album"
          error={formErrors.name}
        />
      </div>
      <div className="mb-3">
        <Textarea
          name="description"
          label="Descripción"
          value={albumData.description}
          onChange={handleChange}
          placeholder="Contanos sobre este viaje..."
          rows={2}
          error={formErrors.description}
        />
      </div>
      <div className="mb-3 grid grid-cols-2 gap-3">
        <Input
          name="startDate"
          label="Desde"
          type="date"
          value={albumData.startDate}
          onChange={handleChange}
          error={formErrors.startDate}
        />
        <Input
          name="endDate"
          label="Hasta"
          type="date"
          value={albumData.endDate}
          onChange={handleChange}
          error={formErrors.endDate}
        />
      </div>
      {error && <p className="mb-3 text-sm text-red-600">{error}</p>}
      <Button
        type="submit"
        loading={loading}
        className="bg-orange-400 text-white transition-transform hover:scale-110 hover:bg-orange-500"
      >
        Crear álbum
      </Button>
    </form>
  );
};

const AdminDashboard = () => {
  const [albums, setAlbums] = useState<AlbumListItemInterface[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [showForm, setShowForm] = useState<boolean>(false);

  const loadAlbums = async () => {
    try {
      const data = await apiGet<AlbumListItemAPIInterface[]>(API_ENDPOINT_URL.ALBUMS_API);

      console.log("data: ", data);

      setAlbums(data.map(parseAlbumListItem));
    } catch (err) {
      console.log("error: ", err);

      setError(err instanceof ApiError ? err.message : ERROR_MESSAGES.ALBUMS_NOT_LOAD);
    }
  };

  useEffect(() => {
    (async () => {
      await loadAlbums();
    })();
  }, []);

  return (
    <div>
      <div className="mb-6 flex items-center justify-between">
        <h1 className="text-[25px] font-semibold text-white md:text-[30px]">Tus álbumes</h1>
        <Button variant="primary" onClick={() => setShowForm((v) => !v)}>
          {showForm ? "Cancelar" : "+ Nuevo álbum"}
        </Button>
      </div>

      {showForm && (
        <NewAlbumForm
          onCreated={() => {
            setShowForm(false);
            loadAlbums();
          }}
        />
      )}

      {error && <p className="mb-4 text-sm text-red-600">{error}</p>}

      {albums === null && !error && <p className="text-sm text-neutral-500">Cargando...</p>}

      {albums !== null && albums.length === 0 && (
        <p className="text-sm text-neutral-500">Todavía no creaste ningún álbum.</p>
      )}

      <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 md:grid-cols-4">
        {albums?.map((album) => (
          <Link
            key={album.id}
            href={`${ROUTES.ALBUM}/${album.id}`}
            className="group overflow-hidden rounded-xl border border-neutral-200 bg-white transition hover:shadow-md"
          >
            <div className="aspect-square bg-neutral-100">
              {album.coverThumbnailUrl ? (
                // eslint-disable-next-line @next/next/no-img-element
                <img
                  src={album.coverThumbnailUrl}
                  alt={album.name}
                  className="h-full w-full object-cover"
                />
              ) : (
                <div className="flex h-full w-full items-center justify-center text-xs text-neutral-400">
                  Sin fotos
                </div>
              )}
            </div>
            <div className="p-3">
              <p className="truncate text-sm font-medium text-neutral-900">{album.name}</p>
              <p className="text-xs text-neutral-500">
                {album.mediaCount} {album.mediaCount === 1 ? "archivo" : "archivos"}
              </p>
            </div>
          </Link>
        ))}
      </div>
    </div>
  );
};

export default AdminDashboard;
