import { useState } from 'react'
import type { SearchLocation } from '../../lib/searchLocation.ts'
import { secondaryButtonClassName } from '../buttonStyles.ts'
import TextField from '../TextField.tsx'

// About 100 meters. Ample for a search measured in miles, and it avoids
// sending a more precise position than the search needs.
const LOCATION_DECIMAL_PLACES = 3

type LocationFieldsProps = {
  location: SearchLocation
  onChange: (location: SearchLocation) => void
}

/** Latitude and longitude inputs with a button that fills them from the browser's location. */
export default function LocationFields({ location, onChange }: LocationFieldsProps) {
  const [locatingState, setLocatingState] = useState<'idle' | 'locating' | 'failed'>('idle')

  function fillInCurrentLocation() {
    if (!('geolocation' in navigator)) {
      setLocatingState('failed')
      return
    }
    setLocatingState('locating')
    navigator.geolocation.getCurrentPosition(
      (position) => {
        onChange({
          latitude: position.coords.latitude.toFixed(LOCATION_DECIMAL_PLACES),
          longitude: position.coords.longitude.toFixed(LOCATION_DECIMAL_PLACES),
        })
        setLocatingState('idle')
      },
      () => setLocatingState('failed'),
    )
  }

  return (
    <fieldset>
      <legend className="text-sm font-medium text-stone-800">Location</legend>
      <div className="mt-2 grid gap-5 sm:grid-cols-[1fr_1fr_auto] sm:items-start">
        <TextField
          label="Latitude"
          name="latitude"
          inputMode="decimal"
          required
          hint="For example 35.227."
          value={location.latitude}
          onChange={(event) => onChange({ ...location, latitude: event.target.value })}
        />
        <TextField
          label="Longitude"
          name="longitude"
          inputMode="decimal"
          required
          hint="For example -80.843."
          value={location.longitude}
          onChange={(event) => onChange({ ...location, longitude: event.target.value })}
        />
        <button
          type="button"
          onClick={fillInCurrentLocation}
          disabled={locatingState === 'locating'}
          className={`sm:mt-6 ${secondaryButtonClassName}`}
        >
          {locatingState === 'locating' ? 'Locating…' : 'Use my current location'}
        </button>
      </div>
      {locatingState === 'failed' && (
        <p role="alert" className="mt-2 text-sm text-red-800">
          Your location could not be determined. Enter your coordinates instead.
        </p>
      )}
    </fieldset>
  )
}
