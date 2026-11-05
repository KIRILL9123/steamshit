export interface MapMetadata {
  displayName: string;
  posX: number;
  posY: number;
  scale: number;
  radarUrl: string;
}

export const MAP_METADATA: Record<string, MapMetadata> = {
  de_mirage: {
    displayName: 'Mirage',
    posX: -3230,
    posY: 1713,
    scale: 5.0,
    radarUrl: 'https://raw.githubusercontent.com/MurkyYT/cs2-map-icons/main/images/radars/de_mirage_radar_psd.png',
  },
  de_inferno: {
    displayName: 'Inferno',
    posX: -2087,
    posY: 3870,
    scale: 4.9,
    radarUrl: 'https://raw.githubusercontent.com/MurkyYT/cs2-map-icons/main/images/radars/de_inferno_radar_psd.png',
  },
  de_nuke: {
    displayName: 'Nuke',
    posX: -3453,
    posY: 2887,
    scale: 7.0,
    radarUrl: 'https://raw.githubusercontent.com/MurkyYT/cs2-map-icons/main/images/radars/de_nuke_radar_psd.png',
  },
  de_ancient: {
    displayName: 'Ancient',
    posX: -2953,
    posY: 2164,
    scale: 5.0,
    radarUrl: 'https://raw.githubusercontent.com/MurkyYT/cs2-map-icons/main/images/radars/de_ancient_radar_psd.png',
  },
  de_anubis: {
    displayName: 'Anubis',
    posX: -2796,
    posY: 3328,
    scale: 5.22,
    radarUrl: 'https://raw.githubusercontent.com/MurkyYT/cs2-map-icons/main/images/radars/de_anubis_radar_psd.png',
  },
  de_dust2: {
    displayName: 'Dust II',
    posX: -2476,
    posY: 3239,
    scale: 4.4,
    radarUrl: 'https://raw.githubusercontent.com/MurkyYT/cs2-map-icons/main/images/radars/de_dust2_radar_psd.png',
  },
  de_vertigo: {
    displayName: 'Vertigo',
    posX: -3168,
    posY: 1762,
    scale: 4.0,
    radarUrl: 'https://raw.githubusercontent.com/MurkyYT/cs2-map-icons/main/images/radars/de_vertigo_radar_psd.png',
  },
  de_overpass: {
    displayName: 'Overpass',
    posX: -4831,
    posY: 1781,
    scale: 5.2,
    radarUrl: 'https://raw.githubusercontent.com/MurkyYT/cs2-map-icons/main/images/radars/de_overpass_radar_psd.png',
  },
  cs_office: {
    displayName: 'Office',
    posX: -1838,
    posY: 1858,
    scale: 4.1,
    radarUrl: 'https://raw.githubusercontent.com/MurkyYT/cs2-map-icons/main/images/radars/cs_office_radar_psd.png',
  },
  cs_italy: {
    displayName: 'Italy',
    posX: -2647,
    posY: 2592,
    scale: 4.6,
    radarUrl: 'https://raw.githubusercontent.com/MurkyYT/cs2-map-icons/main/images/radars/cs_italy_radar_psd.png',
  },
  de_cache: {
    displayName: 'Cache',
    posX: -2000,
    posY: 3250,
    scale: 5.5,
    radarUrl: 'https://raw.githubusercontent.com/MurkyYT/cs2-map-icons/main/images/radars/de_cache_radar_psd.png',
  },
};
