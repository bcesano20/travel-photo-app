"use client";

import { useEffect, useState } from "react";

import { API_ENDPOINT_URL, ERROR_MESSAGES } from "@/helpers/constants";
import { AlbumDataInterface, AlbumDetailAPIInterface } from "@/helpers/interfaces";
import { parseAlbumDetail } from "@/helpers/apiParsers";
import { apiGet, apiPatch } from "@/helpers/apiHelper";
import { Button } from "./Button";
import { Input } from "./Input";
import { Textarea } from "./Textarea";

const ALBUM_DATA_DEFAULT: AlbumDataInterface = {
  name: "",
  description: "",
  startDate: "",
  endDate: "",
};

type AlbumFormErrors = Partial<Record<keyof AlbumDataInterface, string>>;

interface EditAlbumModalProps {
  albumId: number | null;
  onClose: () => void;
  onUpdated: () => void;
}

export const EditAlbumModal = ({ albumId, onClose, onUpdated }: EditAlbumModalProps) => {
  const [albumData, setAlbumData] = useState<AlbumDataInterface>(ALBUM_DATA_DEFAULT);
  const [formErrors, setFormErrors] = useState<AlbumFormErrors>({});

  const [loadingAlbum, setLoadingAlbum] = useState<boolean>(false);
  const [loading, setLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (albumId === null) return;

    (async () => {
      setLoadingAlbum(true);
      setError(null);
      try {
        const data = await apiGet<AlbumDetailAPIInterface>(
          `${API_ENDPOINT_URL.ALBUMS_API}${albumId}/`,
        );
        const album = parseAlbumDetail(data);
        setAlbumData({
          name: album.name,
          description: album.description,
          startDate: album.startDate ?? "",
          endDate: album.endDate ?? "",
        });
      } catch {
        setError(ERROR_MESSAGES.ALBUMS_NOT_LOAD);
      } finally {
        setLoadingAlbum(false);
      }
    })();
  }, [albumId]);

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

  const handleClose = () => {
    setAlbumData(ALBUM_DATA_DEFAULT);
    setFormErrors({});
    setError(null);
    onClose();
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (albumId === null || !isValidForm()) return;

    setLoading(true);
    setError(null);
    try {
      await apiPatch(`${API_ENDPOINT_URL.ALBUMS_API}${albumId}/`, {
        name: albumData.name,
        description: albumData.description,
        start_date: albumData.startDate || null,
        end_date: albumData.endDate || null,
      });
      onUpdated();
    } catch {
      setError(ERROR_MESSAGES.ALBUM_NOT_UPDATED);
    } finally {
      setLoading(false);
    }
  };

  if (albumId === null) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
      <div className="w-full max-w-md rounded-xl border border-neutral-200 bg-white p-4">
        <div className="mb-3 flex items-center justify-between">
          <h2 className="text-foreground text-[28px] font-semibold md:text-[38px]">Editar álbum</h2>
          <button
            type="button"
            onClick={handleClose}
            aria-label="Cerrar"
            className="cursor-pointer text-xl text-neutral-400 hover:text-neutral-700"
          >
            ✕
          </button>
        </div>

        {loadingAlbum ? (
          <p className="text-sm text-neutral-500">Cargando...</p>
        ) : (
          <form onSubmit={handleSubmit}>
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
              className="bg-orange-400 text-white hover:bg-orange-500"
            >
              Guardar cambios
            </Button>
          </form>
        )}
      </div>
    </div>
  );
};
