import { LayerExtension } from "@deck.gl/core";
import type { Layer, LayerContext } from "@deck.gl/core";

/**
 * GPU time filter for every building layer.
 *
 * Each building carries (year built, year gone, mode). The current year is one uniform, so moving
 * through time never touches the vertex buffers: the vertex shader hides what does not exist yet
 * or no longer does, and lets new buildings rise from the ground over `rise` years (mode 0) or
 * simply appear in place (mode 1, used for landmark models that go up piece by piece). The
 * fragment shader gives fresh construction a warm tint that fades over `glow` years.
 *
 * Two optional extras:
 *  - near rectangle: generated boxes flagged "covered" (anchor.z = 1) disappear from `nearYear`
 *    inside the lng/lat rectangle where real building shapes are on screen instead;
 *  - tint: mixes every fragment toward one colour (the ground layer uses it to follow the
 *    historic style of the base map).
 */
const uniformBlock = /* glsl */ `\
layout(std140) uniform cityTimeUniforms {
  float year;
  float rise;
  float glow;
  float glowStrength;
  vec4 nearRect;
  vec4 tint;
  float nearYear;
} cityTime;
`;

const cityTimeModule = {
  name: "cityTime",
  vs: /* glsl */ `
${uniformBlock}
in vec3 cityLife;
in vec3 cityAnchor;
out float cityTime_visible;
out float cityTime_fresh;
`,
  fs: /* glsl */ `
${uniformBlock}
in float cityTime_visible;
in float cityTime_fresh;
`,
  inject: {
    "vs:DECKGL_FILTER_GL_POSITION": /* glsl */ `
    float ct_end = cityLife.y;
    if (cityAnchor.z > 0.5 && cityTime.nearYear > -9000.0 &&
        cityAnchor.x > cityTime.nearRect.x && cityAnchor.x < cityTime.nearRect.z &&
        cityAnchor.y > cityTime.nearRect.y && cityAnchor.y < cityTime.nearRect.w) {
      ct_end = min(ct_end, cityTime.nearYear);
    }
    float ct_age = cityTime.year - cityLife.x;
    float ct_grow = clamp(ct_age / cityTime.rise, 0.0, 1.0);
    ct_grow = ct_grow * ct_grow * (3.0 - 2.0 * ct_grow);
    float ct_gone = clamp((cityTime.year - ct_end) / cityTime.rise, 0.0, 1.0);
    cityTime_visible = (ct_age >= 0.0 && ct_gone < 1.0) ? 1.0 : 0.0;
    cityTime_fresh = 1.0 - clamp(ct_age / cityTime.glow, 0.0, 1.0);
    if (cityLife.z < 0.5) {
      vec4 ct_common = geometry.position;
      ct_common.z *= ct_grow * (1.0 - ct_gone);
      position = project_common_position_to_clipspace(ct_common);
    }
    if (cityTime_visible < 0.5) {
      position = vec4(0.0);
    }
    `,
    "fs:DECKGL_FILTER_COLOR": /* glsl */ `
    if (cityTime_visible < 0.5) discard;
    color.rgb = mix(color.rgb, cityTime.tint.rgb, cityTime.tint.a);
    color.rgb = mix(color.rgb, vec3(1.0, 0.86, 0.6), cityTime_fresh * cityTime.glowStrength);
    `,
  },
  uniformTypes: {
    year: "f32",
    rise: "f32",
    glow: "f32",
    glowStrength: "f32",
    nearRect: "vec4<f32>",
    tint: "vec4<f32>",
    nearYear: "f32",
  },
} as const;

export interface CityTimeProps {
  /** current year (fractional) */
  cityYear?: number;
  /** years a building takes to rise from the ground */
  cityRise?: number;
  /** years the "fresh construction" tint takes to fade */
  cityGlow?: number;
  cityGlowStrength?: number;
  /** [west, south, east, north] in degrees where real shapes are shown, or null */
  cityNearRect?: [number, number, number, number] | null;
  /** year from which covered boxes give way inside the near rectangle */
  cityNearYear?: number;
  /** [r, g, b, mix] with channels 0..1 */
  cityTint?: [number, number, number, number];
}

export class CityTimeExtension extends LayerExtension {
  static extensionName = "CityTimeExtension";
  static defaultProps = {
    getLife: { type: "accessor", value: [0, 32767, 0] },
    getAnchor: { type: "accessor", value: [0, 0, 0] },
    cityYear: 2026,
    cityRise: 2,
    cityGlow: 8,
    cityGlowStrength: 0.7,
    cityNearRect: null,
    cityNearYear: 1975,
    cityTint: [0, 0, 0, 0],
  };

  getShaders(this: Layer) {
    return { modules: [cityTimeModule] };
  }

  initializeState(this: Layer, _context: LayerContext, _extension: this) {
    this.getAttributeManager()?.add({
      cityLife: { size: 3, type: "float32", stepMode: "dynamic", accessor: "getLife" },
      cityAnchor: { size: 3, type: "float32", stepMode: "dynamic", accessor: "getAnchor" },
    });
  }

  draw(this: Layer<CityTimeProps>, _params: unknown, _extension: this) {
    const { cityYear = 2026, cityRise = 2, cityGlow = 8, cityGlowStrength = 0.7, cityNearRect = null, cityNearYear = 1975, cityTint = [0, 0, 0, 0] } = this.props;
    this.setShaderModuleProps({
      cityTime: {
        year: cityYear,
        rise: Math.max(cityRise, 1e-3),
        glow: Math.max(cityGlow, 1e-3),
        glowStrength: cityGlowStrength,
        nearRect: cityNearRect ?? [0, 0, 0, 0],
        tint: cityTint,
        nearYear: cityNearRect ? cityNearYear : -10000,
      },
    });
  }
}
