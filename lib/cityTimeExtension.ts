import { LayerExtension } from "@deck.gl/core";
import type { Layer, LayerContext } from "@deck.gl/core";

/**
 * GPU time filter for the building layer.
 *
 * Every building carries (year built, year replaced). The current year is a single uniform, so
 * moving through time never touches the vertex buffers: the vertex shader hides buildings that
 * do not exist yet (or no longer do), lets new ones rise from the ground over `rise` years, and
 * the fragment shader gives fresh construction a warm tint that fades over `glow` years.
 */
const uniformBlock = /* glsl */ `\
layout(std140) uniform cityTimeUniforms {
  float year;
  float rise;
  float glow;
  float glowStrength;
} cityTime;
`;

const cityTimeModule = {
  name: "cityTime",
  vs: /* glsl */ `
${uniformBlock}
in vec2 cityLife;
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
    float ct_age = cityTime.year - cityLife.x;
    float ct_grow = clamp(ct_age / cityTime.rise, 0.0, 1.0);
    ct_grow = ct_grow * ct_grow * (3.0 - 2.0 * ct_grow);
    float ct_gone = clamp((cityTime.year - cityLife.y) / cityTime.rise, 0.0, 1.0);
    cityTime_visible = (ct_age >= 0.0 && ct_gone < 1.0) ? 1.0 : 0.0;
    cityTime_fresh = 1.0 - clamp(ct_age / cityTime.glow, 0.0, 1.0);
    vec4 ct_common = geometry.position;
    ct_common.z *= ct_grow * (1.0 - ct_gone);
    position = project_common_position_to_clipspace(ct_common);
    if (cityTime_visible < 0.5) {
      position = vec4(0.0);
    }
    `,
    "fs:DECKGL_FILTER_COLOR": /* glsl */ `
    if (cityTime_visible < 0.5) discard;
    color.rgb = mix(color.rgb, vec3(1.0, 0.86, 0.6), cityTime_fresh * cityTime.glowStrength);
    `,
  },
  uniformTypes: {
    year: "f32",
    rise: "f32",
    glow: "f32",
    glowStrength: "f32",
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
}

export class CityTimeExtension extends LayerExtension {
  static extensionName = "CityTimeExtension";
  static defaultProps = {
    getLife: { type: "accessor", value: [0, 32767] },
    cityYear: 2026,
    cityRise: 2,
    cityGlow: 8,
    cityGlowStrength: 0.7,
  };

  getShaders(this: Layer) {
    return { modules: [cityTimeModule] };
  }

  initializeState(this: Layer, _context: LayerContext, _extension: this) {
    this.getAttributeManager()?.add({
      cityLife: { size: 2, type: "float32", stepMode: "dynamic", accessor: "getLife" },
    });
  }

  draw(this: Layer<CityTimeProps>, _params: unknown, _extension: this) {
    const { cityYear = 2026, cityRise = 2, cityGlow = 8, cityGlowStrength = 0.7 } = this.props;
    this.setShaderModuleProps({
      cityTime: {
        year: cityYear,
        rise: Math.max(cityRise, 1e-3),
        glow: Math.max(cityGlow, 1e-3),
        glowStrength: cityGlowStrength,
      },
    });
  }
}
