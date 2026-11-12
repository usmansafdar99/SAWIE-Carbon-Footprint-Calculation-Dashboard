"""
Carbon Footprint Calculation Engine for Cotton Production

Emission factors based on:
- IPCC guidelines
- Cool Farm Tool methodology
- Regional Pakistan agricultural data
"""

from typing import Dict, List, Tuple
from dataclasses import dataclass

@dataclass
class EmissionFactor:
    """Emission factor for a process"""
    value: float
    unit: str  # e.g., "kg CO2e/kg", "kg CO2e/L", "kg CO2e/hour"
    description: str

class CarbonCalculator:
    """Main carbon calculation engine"""
    
    # Emission factors (kg CO2e per unit)
    FACTORS = {
        # Fertiliser (kg CO2e per kg nutrient)
        'fertiliser': {
            'urea': 1.9,
            'ammonium_nitrate': 3.1,
            'ammonium_sulphate': 2.5,
            'diammonium_phosphate': 2.8,
            'single_super_phosphate': 0.85,
            'potassium_chloride': 0.73,
            'manure': 0.3,
        },
        
        # Irrigation (kg CO2e per mm applied per hectare)
        'irrigation': {
            'furrow': 0.42,
            'sprinkler': 0.78,
            'drip': 0.52,
            'flood': 0.35,
            'canal': 0.25,
        },
        
        # Machinery & fuel (kg CO2e per liter)
        'diesel': 3.15,
        'petrol': 2.31,
        'electricity': 0.9,  # kg CO2e per kWh (Pakistan grid average)
        
        # Operations (kg CO2e per hour for different operations)
        'machinery_operations': {
            'ploughing': 8.5,
            'harrowing': 4.2,
            'weeding': 3.5,
            'spraying': 2.1,
            'harvesting': 6.8,
        },
        
        # Crop protection (kg CO2e per kg active ingredient)
        'pest_protection': {
            'insecticide': 12.5,
            'fungicide': 8.3,
            'herbicide': 6.8,
            'growth_regulator': 4.2,
        },
        
        # Residue (kg CO2e per ton)
        'residue': {
            'burning': 1800,      # High emissions from burning
            'incorporation': 200, # Lower emissions from decomposition
            'removal': 50,        # Lowest emissions
            'composting': 100,
        },
        
        # Land use and soil
        'land_preparation': 0.5,  # kg CO2e per hectare per mm of water used
        'soil_factor': {
            'sandy': 1.2,
            'loam': 1.0,
            'clay': 0.8,
        }
    }
    
    # National average benchmark (kg CO2e/kg seed cotton)
    NATIONAL_AVERAGE_INTENSITY = 4.75
    
    def calculate_fertiliser_emissions(
        self, 
        products: List[Dict],
        area_hectares: float
    ) -> Tuple[float, List[Dict]]:
        """
        Calculate emissions from fertiliser use
        
        Args:
            products: List of {product, rate, unit} where rate is kg/acre
            area_hectares: Farm area in hectares
        
        Returns:
            (total_emissions, breakdown)
        """
        total_emissions = 0
        breakdown = []
        
        for product_data in products:
            if not product_data.get('product'):
                continue
                
            product = product_data.get('product', '').lower()
            rate_per_acre = product_data.get('rate', 0)
            
            # Convert to kg per hectare (1 hectare = 2.47 acres)
            rate_per_hectare = rate_per_acre * 2.47
            
            # Get emission factor
            factor = self.FACTORS['fertiliser'].get(product, 1.5)  # Default factor
            
            # Calculate emissions based on nutrient content
            nutrient_content = self._get_nutrient_content(product)
            # rate_per_hectare (kg product) * nutrient_content% / 100 = kg nutrient
            # kg nutrient * factor = kg CO2e per hectare
            emissions_per_hectare = rate_per_hectare * (nutrient_content / 100) * factor
            total_product_emissions = emissions_per_hectare * area_hectares
            
            total_emissions += total_product_emissions
            
            breakdown.append({
                'product': product,
                'rate': rate_per_acre,
                'emissions': total_product_emissions,
                'description': f"{product} at {rate_per_acre} kg/acre"
            })
        
        return total_emissions, breakdown
    
    def calculate_irrigation_emissions(
        self,
        method: str,
        water_applied_mm: float,
        area_hectares: float,
        num_applications: int = 1
    ) -> Tuple[float, Dict]:
        """
        Calculate emissions from irrigation
        
        Args:
            method: irrigation method (furrow, sprinkler, drip, etc.)
            water_applied_mm: water applied per application in mm
            area_hectares: farm area in hectares
            num_applications: number of irrigation events
        
        Returns:
            (total_emissions, breakdown)
        """
        method_lower = method.lower().replace(' ', '_')
        factor = self.FACTORS['irrigation'].get(method_lower, 0.5)  # Default
        
        # Total emissions = factor (kg CO2e/mm/ha) * water_mm * area_ha * applications
        total_emissions = factor * water_applied_mm * area_hectares * num_applications
        
        breakdown = {
            'method': method,
            'water_applied_mm': water_applied_mm,
            'num_applications': num_applications,
            'emissions': total_emissions,
            'description': f"{method} irrigation - {water_applied_mm}mm over {num_applications} applications"
        }
        
        return total_emissions, breakdown
    
    def calculate_machinery_emissions(
        self,
        operations: List[Dict],
        area_hectares: float
    ) -> Tuple[float, List[Dict]]:
        """
        Calculate emissions from machinery and fuel use
        
        Args:
            operations: List of {operation, fuel_type, fuel_consumed}
            area_hectares: farm area in hectares
        
        Returns:
            (total_emissions, breakdown)
        """
        total_emissions = 0
        breakdown = []
        
        for op in operations:
            if not op.get('fuel_type'):
                continue
            
            fuel_type = op.get('fuel_type', '').lower()
            fuel_consumed = op.get('fuel_consumed', 0)
            operation = op.get('operation', 'machinery')
            
            # Get fuel emission factor (kg CO2e per litre)
            fuel_factor = self.FACTORS.get(fuel_type, 3.15)  # Default to diesel
            
            # Calculate emissions
            emissions = fuel_consumed * fuel_factor
            total_emissions += emissions
            
            breakdown.append({
                'operation': operation,
                'fuel_type': fuel_type,
                'fuel_consumed': fuel_consumed,
                'emissions': emissions,
                'description': f"{operation} using {fuel_consumed}L of {fuel_type}"
            })
        
        return total_emissions, breakdown
    
    def calculate_pest_protection_emissions(
        self,
        products: List[Dict]
    ) -> Tuple[float, List[Dict]]:
        """
        Calculate emissions from crop protection products
        
        Args:
            products: List of {product_name, quantity, unit}
        
        Returns:
            (total_emissions, breakdown)
        """
        total_emissions = 0
        breakdown = []
        
        for product in products:
            if not product.get('product_name'):
                continue
            
            product_name = product.get('product_name', '').lower()
            quantity = product.get('quantity', 0)
            
            # Categorize product
            if 'insect' in product_name:
                factor = self.FACTORS['pest_protection']['insecticide']
            elif 'fung' in product_name:
                factor = self.FACTORS['pest_protection']['fungicide']
            elif 'herb' in product_name:
                factor = self.FACTORS['pest_protection']['herbicide']
            else:
                factor = 8.0  # Default
            
            emissions = quantity * factor
            total_emissions += emissions
            
            breakdown.append({
                'product': product_name,
                'quantity': quantity,
                'emissions': emissions,
                'description': f"{product_name} - {quantity}kg"
            })
        
        return total_emissions, breakdown
    
    def calculate_residue_emissions(
        self,
        management_type: str,
        quantity_tons: float
    ) -> Tuple[float, Dict]:
        """
        Calculate emissions from residue management
        
        Args:
            management_type: burning, incorporation, removal, composting
            quantity_tons: quantity of residue in tons
        
        Returns:
            (total_emissions, breakdown)
        """
        management_lower = management_type.lower().replace(' ', '_')
        factor = self.FACTORS['residue'].get(management_lower, 200)  # kg CO2e per ton
        
        # factor is in kg CO2e/ton, quantity in tons -> result in kg CO2e
        total_emissions = quantity_tons * factor
        
        breakdown = {
            'management': management_type,
            'quantity': quantity_tons,
            'emissions': total_emissions,
            'description': f"Residue {management_type} - {quantity_tons} tons"
        }
        
        return total_emissions, breakdown
    
    def calculate_total_footprint(
        self,
        farm_data: Dict,
        season_data: Dict
    ) -> Dict:
        """
        Calculate total carbon footprint for a farm season
        
        Returns:
            {
                'total_co2_equiv': total kg CO2e,
                'intensity_per_kg': kg CO2e per kg seed cotton,
                'emissions_breakdown': {source: value},
                'comparison_percentage': % above/below national average
            }
        """
        area_hectares = farm_data['area'] * 0.404686  # Convert acres to hectares
        
        # Initialize totals
        total_emissions = 0
        emissions_by_source = {}
        
        # 1. Fertiliser emissions
        fert_data = season_data.get('fertiliser_data', {})
        if fert_data and isinstance(fert_data, dict):
            products = fert_data.get('products', []) or [fert_data]
            if products and not isinstance(products[0], dict):
                products = [fert_data]
            fert_emissions, _ = self.calculate_fertiliser_emissions(products, area_hectares)
        else:
            fert_emissions = 0
        emissions_by_source['fertiliser'] = fert_emissions
        total_emissions += fert_emissions
        
        # 2. Irrigation emissions
        irrig_data = season_data.get('irrigation_data', {})
        if irrig_data:
            method = irrig_data.get('method', 'furrow')
            water = irrig_data.get('water_applied', 500)
            apps = irrig_data.get('number_of_applications', 5)
            irrig_emissions, _ = self.calculate_irrigation_emissions(
                method, water, area_hectares, apps
            )
        else:
            irrig_emissions = 0
        emissions_by_source['irrigation'] = irrig_emissions
        total_emissions += irrig_emissions
        
        # 3. Machinery emissions
        mach_data = season_data.get('machinery_data', {})
        if mach_data:
            operations = mach_data.get('operations', []) or [mach_data]
            if operations and not isinstance(operations[0], dict):
                operations = [mach_data]
            mach_emissions, _ = self.calculate_machinery_emissions(operations, area_hectares)
        else:
            mach_emissions = 0
        emissions_by_source['machinery'] = mach_emissions
        total_emissions += mach_emissions
        
        # 4. Crop protection emissions
        pest_data = season_data.get('pest_protection_data', {})
        if pest_data:
            products = pest_data.get('products', []) or [pest_data]
            if products and not isinstance(products[0], dict):
                products = [pest_data]
            pest_emissions, _ = self.calculate_pest_protection_emissions(products)
        else:
            pest_emissions = 0
        emissions_by_source['crop_protection'] = pest_emissions
        total_emissions += pest_emissions
        
        # 5. Residue management emissions
        resid_data = season_data.get('residue_data', {})
        if resid_data:
            mgmt = resid_data.get('management_type', 'incorporation')
            qty = resid_data.get('quantity', 5)
            resid_emissions, _ = self.calculate_residue_emissions(mgmt, qty)
        else:
            resid_emissions = 0
        emissions_by_source['residue'] = resid_emissions
        total_emissions += resid_emissions
        
        # FIX: Calculate intensity correctly (kg CO2e / kg seed cotton)
        # yield_kg = kg per acre * harvested acres = total kg
        yield_kg = season_data.get('seed_cotton_yield', 1000) * farm_data['harvested_area']
        intensity = (total_emissions / yield_kg) if yield_kg > 0 else 0
        
        # Calculate comparison vs national average
        comparison = ((intensity - self.NATIONAL_AVERAGE_INTENSITY) / self.NATIONAL_AVERAGE_INTENSITY) * 100
        
        return {
            'total_co2_equiv': total_emissions,
            'intensity_per_kg': intensity,
            'emissions_breakdown': {
                'fertiliser': emissions_by_source['fertiliser'],
                'irrigation': emissions_by_source['irrigation'],
                'machinery': emissions_by_source['machinery'],
                'crop_protection': emissions_by_source['crop_protection'],
                'residue': emissions_by_source['residue'],
            },
            'comparison_percentage': comparison,
            'national_average_intensity': self.NATIONAL_AVERAGE_INTENSITY
        }
    
    def _get_nutrient_content(self, fertiliser: str) -> float:
        """Get nutrient content % for common fertilisers"""
        nutrient_map = {
            'urea': 46,              # 46% nitrogen
            'ammonium_nitrate': 34,
            'ammonium_sulphate': 21,
            'diammonium_phosphate': 46,  # 46% P2O5
            'single_super_phosphate': 18,
            'potassium_chloride': 60,
            'manure': 3,
        }
        return nutrient_map.get(fertiliser, 30)
