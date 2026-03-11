"""
Weekly Report Generator for Price Tracker

This module generates comprehensive weekly price reports with:
- Price history charts for all tracked products
- Statistics (min, max, average, trend analysis)
- Best deals identification
- Scraper run statistics
- HTML email reports with embedded charts

Author: Price Tracker Team
Phase: 5 (Weekly Reports)
"""

import io
import base64
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, Tuple
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import smtplib

import matplotlib
matplotlib.use('Agg')  # Use non-interactive backend for server environments
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from matplotlib.figure import Figure

from sqlalchemy.orm import Session
from sqlalchemy import func, desc

from database.models import Product, Price, ScraperRun, AlertSent
from database.connection import get_session

logger = logging.getLogger(__name__)


class ReportGenerator:
    """
    Generates weekly price reports with charts and statistics.
    
    Features:
    - Price history visualization with matplotlib
    - Statistical analysis (min/max/avg/trend)
    - Best deals identification
    - Scraper performance metrics
    - HTML email generation with embedded charts
    """
    
    def __init__(self, config: Dict[str, Any], db_session: Session):
        """
        Initialize the report generator.
        
        Args:
            config: Application configuration dictionary
            db_session: SQLAlchemy database session
        """
        self.config = config
        self.session = db_session
        self.report_config = config.get('reports', {})
        self.email_config = config.get('alerts', {}).get('email', {})
        
        # Report settings
        self.days_to_include = self.report_config.get('days_to_include', 7)
        self.chart_width = self.report_config.get('chart_width', 10)
        self.chart_height = self.report_config.get('chart_height', 6)
        self.dpi = self.report_config.get('dpi', 100)
        self.top_deals_count = self.report_config.get('top_deals_count', 5)
        
        # Validate email configuration
        if not self.email_config.get('enabled', False):
            logger.warning("Email not enabled in configuration")
        
        logger.info(f"ReportGenerator initialized for {self.days_to_include}-day reports")
    
    def generate_weekly_report(self, send_email: bool = True) -> Dict[str, Any]:
        """
        Generate a complete weekly report with charts and statistics.
        
        Args:
            send_email: Whether to send the report via email
        
        Returns:
            Dictionary with report generation results
        """
        logger.info("=== Starting Weekly Report Generation ===")
        
        try:
            # Calculate date range
            end_date = datetime.now()
            start_date = end_date - timedelta(days=self.days_to_include)
            
            logger.info(f"Report period: {start_date.date()} to {end_date.date()}")
            
            # Get all products
            products = self.session.query(Product).all()
            
            if not products:
                logger.warning("No active products found")
                return {
                    'success': False,
                    'error': 'No active products to report on',
                    'products_analyzed': 0
                }
            
            logger.info(f"Analyzing {len(products)} active products")
            
            # Generate product reports
            product_reports = []
            for product in products:
                report = self._generate_product_report(product, start_date, end_date)
                if report:
                    product_reports.append(report)
            
            # Get scraper statistics
            scraper_stats = self._get_scraper_statistics(start_date, end_date)
            
            # Generate charts
            charts = self._generate_charts(product_reports)
            
            # Create HTML report
            html_content = self._create_html_report(
                product_reports, 
                scraper_stats, 
                charts, 
                start_date, 
                end_date
            )
            
            result = {
                'success': True,
                'products_analyzed': len(product_reports),
                'period_start': start_date.isoformat(),
                'period_end': end_date.isoformat(),
                'charts_generated': len(charts),
                'html_size': len(html_content)
            }
            
            # Send email if requested
            if send_email and self.email_config.get('enabled', False):
                email_result = self._send_report_email(html_content, start_date, end_date)
                result['email_sent'] = email_result['success']
                if not email_result['success']:
                    result['email_error'] = email_result.get('error')
            else:
                result['email_sent'] = False
                result['email_reason'] = 'Email not enabled or send_email=False'
            
            logger.info(f"Report generation complete: {result}")
            return result
            
        except Exception as e:
            logger.error(f"Error generating weekly report: {str(e)}", exc_info=True)
            return {
                'success': False,
                'error': str(e)
            }
    
    def _generate_product_report(
        self, 
        product: Product, 
        start_date: datetime, 
        end_date: datetime
    ) -> Optional[Dict[str, Any]]:
        """
        Generate report data for a single product.
        
        Args:
            product: Product model instance
            start_date: Report start date
            end_date: Report end date
        
        Returns:
            Dictionary with product report data, or None if no data
        """
        try:
            # Get prices within date range
            prices = (
                self.session.query(Price)
                .filter(
                    Price.product_id == product.id,
                    Price.scraped_at >= start_date,
                    Price.scraped_at <= end_date
                )
                .order_by(Price.scraped_at)
                .all()
            )
            
            if not prices:
                logger.debug(f"No prices found for product {product.id} in date range")
                return None
            
            # Calculate statistics
            price_values = [p.price for p in prices]
            current_price = price_values[-1]
            min_price = min(price_values)
            max_price = max(price_values)
            avg_price = sum(price_values) / len(price_values)
            
            # Calculate price trend
            if len(price_values) >= 2:
                first_price = price_values[0]
                last_price = price_values[-1]
                price_change = last_price - first_price
                price_change_pct = (price_change / first_price) * 100 if first_price > 0 else 0
                
                if price_change_pct > 2:
                    trend = 'increasing'
                elif price_change_pct < -2:
                    trend = 'decreasing'
                else:
                    trend = 'stable'
            else:
                price_change = 0
                price_change_pct = 0
                trend = 'stable'
            
            # Calculate savings (current vs max)
            savings_amount = max_price - current_price if current_price < max_price else 0
            savings_pct = (savings_amount / max_price) * 100 if max_price > 0 else 0
            
            # Count alerts sent for this product
            alerts_count = (
                self.session.query(func.count(AlertSent.id))
                .join(Product)
                .filter(
                    Product.id == product.id,
                    AlertSent.sent_at >= start_date,
                    AlertSent.sent_at <= end_date
                )
                .scalar() or 0
            )
            
            return {
                'product': product,
                'prices': prices,
                'current_price': current_price,
                'min_price': min_price,
                'max_price': max_price,
                'avg_price': avg_price,
                'price_change': price_change,
                'price_change_pct': price_change_pct,
                'trend': trend,
                'savings_amount': savings_amount,
                'savings_pct': savings_pct,
                'alerts_count': alerts_count,
                'data_points': len(prices)
            }
            
        except Exception as e:
            logger.error(f"Error generating report for product {product.id}: {str(e)}")
            return None
    
    def _get_scraper_statistics(
        self, 
        start_date: datetime, 
        end_date: datetime
    ) -> Dict[str, Any]:
        """
        Get scraper run statistics for the reporting period.
        
        Args:
            start_date: Report start date
            end_date: Report end date
        
        Returns:
            Dictionary with scraper statistics
        """
        try:
            # Get all scraper runs in period
            runs = (
                self.session.query(ScraperRun)
                .filter(
                    ScraperRun.started_at >= start_date,
                    ScraperRun.started_at <= end_date
                )
                .all()
            )
            
            if not runs:
                return {
                    'total_runs': 0,
                    'successful_runs': 0,
                    'failed_runs': 0,
                    'success_rate': 0,
                    'total_products': 0,
                    'avg_duration': 0
                }
            
            successful_runs = [r for r in runs if r.status == 'completed']
            failed_runs = [r for r in runs if r.status == 'failed']
            
            total_products = sum(r.products_scraped for r in successful_runs)
            
            # Calculate average duration (in seconds)
            durations = [
                (r.completed_at - r.started_at).total_seconds() 
                for r in successful_runs 
                if r.completed_at
            ]
            avg_duration = sum(durations) / len(durations) if durations else 0
            
            return {
                'total_runs': len(runs),
                'successful_runs': len(successful_runs),
                'failed_runs': len(failed_runs),
                'success_rate': (len(successful_runs) / len(runs)) * 100,
                'total_products': total_products,
                'avg_duration': avg_duration
            }
            
        except Exception as e:
            logger.error(f"Error getting scraper statistics: {str(e)}")
            return {
                'total_runs': 0,
                'successful_runs': 0,
                'failed_runs': 0,
                'success_rate': 0,
                'total_products': 0,
                'avg_duration': 0,
                'error': str(e)
            }
    
    def _generate_charts(self, product_reports: List[Dict[str, Any]]) -> Dict[str, str]:
        """
        Generate all charts and return them as base64-encoded PNG images.
        
        Args:
            product_reports: List of product report dictionaries
        
        Returns:
            Dictionary mapping chart names to base64-encoded PNG strings
        """
        charts = {}
        
        try:
            # Chart 1: Price history for each product (combined or individual)
            if len(product_reports) <= 3:
                # If 3 or fewer products, create individual charts
                for i, report in enumerate(product_reports):
                    chart_name = f"price_history_{i}"
                    charts[chart_name] = self._generate_price_chart(report)
            else:
                # If many products, create a comparison chart
                charts['price_comparison'] = self._generate_price_comparison_chart(product_reports)
            
            # Chart 2: Savings opportunities
            if any(r['savings_amount'] > 0 for r in product_reports):
                charts['savings'] = self._generate_savings_chart(product_reports)
            
            logger.info(f"Generated {len(charts)} charts")
            
        except Exception as e:
            logger.error(f"Error generating charts: {str(e)}", exc_info=True)
        
        return charts
    
    def _generate_price_chart(self, report: Dict[str, Any]) -> str:
        """
        Generate a price history chart for a single product.
        
        Args:
            report: Product report dictionary
        
        Returns:
            Base64-encoded PNG image
        """
        try:
            product = report['product']
            prices = report['prices']
            
            # Create figure
            fig, ax = plt.subplots(figsize=(self.chart_width, self.chart_height))
            
            # Extract dates and prices
            dates = [p.scraped_at for p in prices]
            price_values = [p.price for p in prices]
            
            # Plot price line
            ax.plot(dates, price_values, marker='o', linewidth=2, markersize=6, color='#2563eb')
            
            # Add min/max annotations
            min_idx = price_values.index(report['min_price'])
            max_idx = price_values.index(report['max_price'])
            
            ax.annotate(
                f'Low: ${report["min_price"]:.2f}',
                xy=(dates[min_idx], report['min_price']),
                xytext=(10, -20),
                textcoords='offset points',
                bbox=dict(boxstyle='round,pad=0.5', fc='#10b981', alpha=0.8),
                arrowprops=dict(arrowstyle='->', connectionstyle='arc3,rad=0', color='#10b981'),
                color='white',
                fontweight='bold'
            )
            
            ax.annotate(
                f'High: ${report["max_price"]:.2f}',
                xy=(dates[max_idx], report['max_price']),
                xytext=(10, 20),
                textcoords='offset points',
                bbox=dict(boxstyle='round,pad=0.5', fc='#ef4444', alpha=0.8),
                arrowprops=dict(arrowstyle='->', connectionstyle='arc3,rad=0', color='#ef4444'),
                color='white',
                fontweight='bold'
            )
            
            # Formatting
            ax.set_xlabel('Date', fontsize=12, fontweight='bold')
            ax.set_ylabel('Price ($)', fontsize=12, fontweight='bold')
            ax.set_title(
                f'{product.name[:50]}...' if len(product.name) > 50 else product.name,
                fontsize=14,
                fontweight='bold',
                pad=20
            )
            ax.grid(True, alpha=0.3, linestyle='--')
            
            # Format x-axis dates
            ax.xaxis.set_major_formatter(mdates.DateFormatter('%m/%d'))
            ax.xaxis.set_major_locator(mdates.DayLocator(interval=1))
            plt.xticks(rotation=45, ha='right')
            
            # Add average line
            ax.axhline(
                y=report['avg_price'],
                color='#f59e0b',
                linestyle='--',
                linewidth=2,
                label=f'Avg: ${report["avg_price"]:.2f}',
                alpha=0.7
            )
            
            ax.legend(loc='upper right', fontsize=10)
            
            plt.tight_layout()
            
            # Convert to base64
            buffer = io.BytesIO()
            plt.savefig(buffer, format='png', dpi=self.dpi, bbox_inches='tight')
            buffer.seek(0)
            image_base64 = base64.b64encode(buffer.read()).decode()
            plt.close(fig)
            
            return image_base64
            
        except Exception as e:
            logger.error(f"Error generating price chart: {str(e)}")
            plt.close('all')
            return ''
    
    def _generate_price_comparison_chart(self, product_reports: List[Dict[str, Any]]) -> str:
        """
        Generate a bar chart comparing current prices across products.
        
        Args:
            product_reports: List of product report dictionaries
        
        Returns:
            Base64-encoded PNG image
        """
        try:
            # Sort by current price
            sorted_reports = sorted(product_reports, key=lambda x: x['current_price'], reverse=True)
            
            # Take top 10 if more than 10 products
            if len(sorted_reports) > 10:
                sorted_reports = sorted_reports[:10]
            
            # Create figure
            fig, ax = plt.subplots(figsize=(self.chart_width, self.chart_height))
            
            # Prepare data
            product_names = [
                r['product'].name[:30] + '...' if len(r['product'].name) > 30 else r['product'].name
                for r in sorted_reports
            ]
            current_prices = [r['current_price'] for r in sorted_reports]
            min_prices = [r['min_price'] for r in sorted_reports]
            max_prices = [r['max_price'] for r in sorted_reports]
            
            # Create bar positions
            x = range(len(product_names))
            width = 0.25
            
            # Create bars
            ax.bar([i - width for i in x], current_prices, width, label='Current', color='#2563eb')
            ax.bar([i for i in x], min_prices, width, label='Lowest', color='#10b981')
            ax.bar([i + width for i in x], max_prices, width, label='Highest', color='#ef4444')
            
            # Formatting
            ax.set_xlabel('Product', fontsize=12, fontweight='bold')
            ax.set_ylabel('Price ($)', fontsize=12, fontweight='bold')
            ax.set_title('Price Comparison Across Products', fontsize=14, fontweight='bold', pad=20)
            ax.set_xticks(x)
            ax.set_xticklabels(product_names, rotation=45, ha='right', fontsize=9)
            ax.legend(loc='upper right', fontsize=10)
            ax.grid(True, alpha=0.3, linestyle='--', axis='y')
            
            plt.tight_layout()
            
            # Convert to base64
            buffer = io.BytesIO()
            plt.savefig(buffer, format='png', dpi=self.dpi, bbox_inches='tight')
            buffer.seek(0)
            image_base64 = base64.b64encode(buffer.read()).decode()
            plt.close(fig)
            
            return image_base64
            
        except Exception as e:
            logger.error(f"Error generating comparison chart: {str(e)}")
            plt.close('all')
            return ''
    
    def _generate_savings_chart(self, product_reports: List[Dict[str, Any]]) -> str:
        """
        Generate a horizontal bar chart showing savings opportunities.
        
        Args:
            product_reports: List of product report dictionaries
        
        Returns:
            Base64-encoded PNG image
        """
        try:
            # Filter products with savings
            savings_reports = [r for r in product_reports if r['savings_amount'] > 0]
            
            if not savings_reports:
                return ''
            
            # Sort by savings amount
            sorted_reports = sorted(savings_reports, key=lambda x: x['savings_amount'], reverse=True)
            
            # Take top N deals
            sorted_reports = sorted_reports[:self.top_deals_count]
            
            # Create figure
            fig, ax = plt.subplots(figsize=(self.chart_width, self.chart_height))
            
            # Prepare data
            product_names = [
                r['product'].name[:40] + '...' if len(r['product'].name) > 40 else r['product'].name
                for r in sorted_reports
            ]
            savings_amounts = [r['savings_amount'] for r in sorted_reports]
            savings_pcts = [r['savings_pct'] for r in sorted_reports]
            
            # Create horizontal bars
            colors = ['#10b981' if pct > 15 else '#f59e0b' if pct > 5 else '#2563eb' 
                     for pct in savings_pcts]
            bars = ax.barh(range(len(product_names)), savings_amounts, color=colors)
            
            # Add percentage labels on bars
            for i, (bar, pct) in enumerate(zip(bars, savings_pcts)):
                width = bar.get_width()
                ax.text(
                    width + 0.5,
                    bar.get_y() + bar.get_height() / 2,
                    f'{pct:.1f}%',
                    ha='left',
                    va='center',
                    fontweight='bold',
                    fontsize=10
                )
            
            # Formatting
            ax.set_xlabel('Savings Amount ($)', fontsize=12, fontweight='bold')
            ax.set_ylabel('Product', fontsize=12, fontweight='bold')
            ax.set_title(
                f'Top {len(sorted_reports)} Savings Opportunities', 
                fontsize=14, 
                fontweight='bold', 
                pad=20
            )
            ax.set_yticks(range(len(product_names)))
            ax.set_yticklabels(product_names, fontsize=9)
            ax.grid(True, alpha=0.3, linestyle='--', axis='x')
            
            plt.tight_layout()
            
            # Convert to base64
            buffer = io.BytesIO()
            plt.savefig(buffer, format='png', dpi=self.dpi, bbox_inches='tight')
            buffer.seek(0)
            image_base64 = base64.b64encode(buffer.read()).decode()
            plt.close(fig)
            
            return image_base64
            
        except Exception as e:
            logger.error(f"Error generating savings chart: {str(e)}")
            plt.close('all')
            return ''
    
    def _create_html_report(
        self,
        product_reports: List[Dict[str, Any]],
        scraper_stats: Dict[str, Any],
        charts: Dict[str, str],
        start_date: datetime,
        end_date: datetime
    ) -> str:
        """
        Create HTML email report with embedded charts.
        
        Args:
            product_reports: List of product report dictionaries
            scraper_stats: Scraper statistics dictionary
            charts: Dictionary of base64-encoded chart images
            start_date: Report start date
            end_date: Report end date
        
        Returns:
            HTML string
        """
        # Calculate overall statistics
        total_products = len(product_reports)
        total_savings = sum(r['savings_amount'] for r in product_reports)
        total_alerts = sum(r['alerts_count'] for r in product_reports)
        
        # Find best deal
        best_deal = max(product_reports, key=lambda x: x['savings_pct']) if product_reports else None
        
        # Sort products by savings for display
        sorted_products = sorted(product_reports, key=lambda x: x['savings_amount'], reverse=True)
        
        html = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Weekly Price Report</title>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
            line-height: 1.6;
            color: #333;
            max-width: 800px;
            margin: 0 auto;
            padding: 20px;
            background-color: #f5f5f5;
        }}
        .container {{
            background: white;
            border-radius: 10px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
            overflow: hidden;
        }}
        .header {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 40px 20px;
            text-align: center;
        }}
        .header h1 {{
            margin: 0;
            font-size: 32px;
            font-weight: 700;
        }}
        .header p {{
            margin: 10px 0 0;
            opacity: 0.9;
            font-size: 16px;
        }}
        .stats-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 20px;
            padding: 30px 20px;
            background: #f9fafb;
        }}
        .stat-box {{
            background: white;
            padding: 20px;
            border-radius: 8px;
            text-align: center;
            box-shadow: 0 1px 3px rgba(0,0,0,0.1);
        }}
        .stat-value {{
            font-size: 32px;
            font-weight: 700;
            color: #667eea;
            margin: 0;
        }}
        .stat-label {{
            font-size: 14px;
            color: #6b7280;
            margin: 5px 0 0;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }}
        .content {{
            padding: 30px 20px;
        }}
        .section {{
            margin-bottom: 40px;
        }}
        .section-title {{
            font-size: 24px;
            font-weight: 700;
            color: #1f2937;
            margin: 0 0 20px;
            padding-bottom: 10px;
            border-bottom: 3px solid #667eea;
        }}
        .product-card {{
            background: #f9fafb;
            border-radius: 8px;
            padding: 20px;
            margin-bottom: 20px;
            border-left: 4px solid #667eea;
        }}
        .product-name {{
            font-size: 18px;
            font-weight: 600;
            color: #1f2937;
            margin: 0 0 15px;
        }}
        .product-stats {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
            gap: 15px;
        }}
        .product-stat {{
            display: flex;
            flex-direction: column;
        }}
        .product-stat-label {{
            font-size: 12px;
            color: #6b7280;
            text-transform: uppercase;
            letter-spacing: 0.5px;
            margin-bottom: 5px;
        }}
        .product-stat-value {{
            font-size: 18px;
            font-weight: 600;
            color: #1f2937;
        }}
        .trend {{
            display: inline-block;
            padding: 4px 12px;
            border-radius: 20px;
            font-size: 12px;
            font-weight: 600;
            text-transform: uppercase;
        }}
        .trend-increasing {{
            background: #fee2e2;
            color: #dc2626;
        }}
        .trend-decreasing {{
            background: #d1fae5;
            color: #059669;
        }}
        .trend-stable {{
            background: #e5e7eb;
            color: #4b5563;
        }}
        .chart {{
            margin: 20px 0;
            text-align: center;
        }}
        .chart img {{
            max-width: 100%;
            height: auto;
            border-radius: 8px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.1);
        }}
        .highlight-box {{
            background: linear-gradient(135deg, #10b981 0%, #059669 100%);
            color: white;
            padding: 20px;
            border-radius: 8px;
            margin: 20px 0;
        }}
        .highlight-box h3 {{
            margin: 0 0 10px;
            font-size: 20px;
        }}
        .highlight-box p {{
            margin: 5px 0;
            font-size: 16px;
        }}
        .footer {{
            background: #f9fafb;
            padding: 20px;
            text-align: center;
            color: #6b7280;
            font-size: 14px;
            border-top: 1px solid #e5e7eb;
        }}
        .btn {{
            display: inline-block;
            padding: 10px 20px;
            background: #667eea;
            color: white;
            text-decoration: none;
            border-radius: 6px;
            font-weight: 600;
            margin: 10px 5px;
        }}
        .btn:hover {{
            background: #5568d3;
        }}
    </style>
</head>
<body>
    <div class="container">
        <!-- Header -->
        <div class="header">
            <h1>📊 Weekly Price Report</h1>
            <p>{start_date.strftime('%B %d, %Y')} - {end_date.strftime('%B %d, %Y')}</p>
        </div>
        
        <!-- Summary Statistics -->
        <div class="stats-grid">
            <div class="stat-box">
                <div class="stat-value">{total_products}</div>
                <div class="stat-label">Products Tracked</div>
            </div>
            <div class="stat-box">
                <div class="stat-value">${total_savings:.2f}</div>
                <div class="stat-label">Potential Savings</div>
            </div>
            <div class="stat-box">
                <div class="stat-value">{total_alerts}</div>
                <div class="stat-label">Price Alerts</div>
            </div>
            <div class="stat-box">
                <div class="stat-value">{scraper_stats['success_rate']:.0f}%</div>
                <div class="stat-label">Scraper Success</div>
            </div>
        </div>
        
        <div class="content">
"""
        
        # Best Deal Highlight
        if best_deal and best_deal['savings_amount'] > 0:
            product = best_deal['product']
            html += f"""
            <div class="highlight-box">
                <h3>🎉 Best Deal of the Week!</h3>
                <p><strong>{product.name}</strong></p>
                <p>Save ${best_deal['savings_amount']:.2f} ({best_deal['savings_pct']:.1f}%)</p>
                <p>Current: ${best_deal['current_price']:.2f} | Was: ${best_deal['max_price']:.2f}</p>
                <a href="{product.url}" class="btn" style="color: white;">View Product</a>
            </div>
"""
        
        # Charts Section
        if charts:
            html += """
            <div class="section">
                <h2 class="section-title">📈 Price Trends</h2>
"""
            for chart_name, chart_data in charts.items():
                if chart_data:
                    html += f"""
                <div class="chart">
                    <img src="data:image/png;base64,{chart_data}" alt="{chart_name}">
                </div>
"""
            html += """
            </div>
"""
        
        # Product Details Section
        html += """
            <div class="section">
                <h2 class="section-title">🏷️ Product Details</h2>
"""
        
        for report in sorted_products:
            product = report['product']
            trend_class = f"trend-{report['trend']}"
            
            html += f"""
                <div class="product-card">
                    <h3 class="product-name">{product.name}</h3>
                    <div class="product-stats">
                        <div class="product-stat">
                            <div class="product-stat-label">Current Price</div>
                            <div class="product-stat-value">${report['current_price']:.2f}</div>
                        </div>
                        <div class="product-stat">
                            <div class="product-stat-label">Week Low</div>
                            <div class="product-stat-value" style="color: #10b981;">${report['min_price']:.2f}</div>
                        </div>
                        <div class="product-stat">
                            <div class="product-stat-label">Week High</div>
                            <div class="product-stat-value" style="color: #ef4444;">${report['max_price']:.2f}</div>
                        </div>
                        <div class="product-stat">
                            <div class="product-stat-label">Average</div>
                            <div class="product-stat-value">${report['avg_price']:.2f}</div>
                        </div>
                        <div class="product-stat">
                            <div class="product-stat-label">Trend</div>
                            <div class="product-stat-value">
                                <span class="trend {trend_class}">{report['trend']}</span>
                            </div>
                        </div>
                        <div class="product-stat">
                            <div class="product-stat-label">Potential Savings</div>
                            <div class="product-stat-value" style="color: #10b981;">${report['savings_amount']:.2f}</div>
                        </div>
                    </div>
                    <div style="margin-top: 15px;">
                        <a href="{product.url}" class="btn">View on {product.source.title()}</a>
                    </div>
                </div>
"""
        
        html += """
            </div>
            
            <!-- Scraper Statistics -->
            <div class="section">
                <h2 class="section-title">🤖 Scraper Performance</h2>
                <div class="product-card">
                    <div class="product-stats">
                        <div class="product-stat">
                            <div class="product-stat-label">Total Runs</div>
                            <div class="product-stat-value">{total_runs}</div>
                        </div>
                        <div class="product-stat">
                            <div class="product-stat-label">Successful</div>
                            <div class="product-stat-value" style="color: #10b981;">{successful_runs}</div>
                        </div>
                        <div class="product-stat">
                            <div class="product-stat-label">Failed</div>
                            <div class="product-stat-value" style="color: #ef4444;">{failed_runs}</div>
                        </div>
                        <div class="product-stat">
                            <div class="product-stat-label">Success Rate</div>
                            <div class="product-stat-value">{success_rate:.1f}%</div>
                        </div>
                        <div class="product-stat">
                            <div class="product-stat-label">Total Data Points</div>
                            <div class="product-stat-value">{total_products_scraped}</div>
                        </div>
                        <div class="product-stat">
                            <div class="product-stat-label">Avg Duration</div>
                            <div class="product-stat-value">{avg_duration:.1f}s</div>
                        </div>
                    </div>
                </div>
            </div>
        </div>
        
        <!-- Footer -->
        <div class="footer">
            <p><strong>Price Tracker</strong> - Automated Price Monitoring System</p>
            <p>Report generated on {end_date.strftime('%B %d, %Y at %I:%M %p')}</p>
        </div>
    </div>
</body>
</html>
""".format(
            total_runs=scraper_stats['total_runs'],
            successful_runs=scraper_stats['successful_runs'],
            failed_runs=scraper_stats['failed_runs'],
            success_rate=scraper_stats['success_rate'],
            total_products_scraped=scraper_stats['total_products'],
            avg_duration=scraper_stats['avg_duration']
        )
        
        return html
    
    def _send_report_email(
        self, 
        html_content: str, 
        start_date: datetime, 
        end_date: datetime
    ) -> Dict[str, Any]:
        """
        Send the report via email.
        
        Args:
            html_content: HTML report content
            start_date: Report start date
            end_date: Report end date
        
        Returns:
            Dictionary with send result
        """
        try:
            # Get email configuration
            smtp_server = self.email_config.get('smtp_server')
            smtp_port = self.email_config.get('smtp_port', 587)
            smtp_username = self.email_config.get('smtp_username', '')
            smtp_password = self.email_config.get('smtp_password', '')
            from_email = self.email_config.get('from_email', smtp_username)
            to_emails = self.email_config.get('to_emails', [])
            
            if not smtp_server or not smtp_username or not smtp_password:
                return {
                    'success': False,
                    'error': 'Email credentials not configured'
                }
            
            if not to_emails:
                return {
                    'success': False,
                    'error': 'No recipient email addresses configured'
                }
            
            # Create message
            msg = MIMEMultipart('alternative')
            msg['Subject'] = f'Weekly Price Report - {start_date.strftime("%b %d")} to {end_date.strftime("%b %d, %Y")}'
            msg['From'] = from_email
            msg['To'] = ', '.join(to_emails)
            
            # Create plain text version
            text_content = f"""
Weekly Price Report
{start_date.strftime('%B %d, %Y')} - {end_date.strftime('%B %d, %Y')}

This is an HTML email. Please view it in an email client that supports HTML.
"""
            
            # Attach both plain text and HTML versions
            part1 = MIMEText(text_content, 'plain')
            part2 = MIMEText(html_content, 'html')
            msg.attach(part1)
            msg.attach(part2)
            
            # Send email
            logger.info(f"Connecting to SMTP server {smtp_server}:{smtp_port}")
            with smtplib.SMTP(smtp_server, smtp_port, timeout=30) as server:
                server.ehlo()
                server.starttls()
                server.ehlo()
                server.login(smtp_username, smtp_password)
                server.send_message(msg)
            
            logger.info(f"Report email sent to {len(to_emails)} recipients")
            
            return {
                'success': True,
                'recipients': to_emails,
                'subject': msg['Subject']
            }
            
        except smtplib.SMTPAuthenticationError as e:
            logger.error(f"SMTP authentication failed: {str(e)}")
            return {
                'success': False,
                'error': f'Authentication failed: {str(e)}'
            }
        except smtplib.SMTPException as e:
            logger.error(f"SMTP error: {str(e)}")
            return {
                'success': False,
                'error': f'SMTP error: {str(e)}'
            }
        except Exception as e:
            logger.error(f"Error sending report email: {str(e)}", exc_info=True)
            return {
                'success': False,
                'error': str(e)
            }


def main():
    """
    Standalone report generation for testing.
    """
    import sys
    from pathlib import Path
    
    # Add project root to path
    project_root = Path(__file__).parent.parent
    sys.path.insert(0, str(project_root))
    
    from utils.config import load_config
    from utils.logging_config import setup_logging
    
    # Setup
    setup_logging()
    config = load_config()
    
    # Generate report
    with get_session() as session:
        generator = ReportGenerator(config, session)
        result = generator.generate_weekly_report(send_email=True)
        
        print("\n" + "="*60)
        print("WEEKLY REPORT GENERATION RESULT")
        print("="*60)
        for key, value in result.items():
            print(f"{key}: {value}")
        print("="*60)


if __name__ == '__main__':
    main()
