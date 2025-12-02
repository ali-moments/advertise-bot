"""
Job Scheduler Example

This example demonstrates how to use the JobScheduler and JobSchedulerCLI
for managing scheduled tasks in the CLI panel.
"""

import asyncio
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from cli.job_scheduler import JobScheduler, JobSchedulerCLI
from cli.config_manager import ConfigManager
from cli.models import JobConfig


async def scrape_links_handler(job_config: JobConfig):
    """
    Example handler for link scraping jobs
    
    In a real implementation, this would call the ScraperCLI.scrape_links()
    method with the parameters from job_config.
    """
    print(f"Executing link scraping job: {job_config.job_id}")
    print(f"  Target channel: {job_config.target_channel}")
    print(f"  Parameters: {job_config.parameters}")
    
    # Simulate scraping operation
    await asyncio.sleep(1)
    
    print(f"Link scraping completed for {job_config.target_channel}")


async def scrape_members_handler(job_config: JobConfig):
    """
    Example handler for member scraping jobs
    """
    print(f"Executing member scraping job: {job_config.job_id}")
    print(f"  Target channel: {job_config.target_channel}")
    print(f"  Parameters: {job_config.parameters}")
    
    # Simulate scraping operation
    await asyncio.sleep(1)
    
    print(f"Member scraping completed for {job_config.target_channel}")


async def main():
    """Main example function"""
    
    # Initialize configuration manager
    config = ConfigManager(config_path='cli/config_example.json')
    await config.load()
    
    # Initialize job scheduler
    scheduler = JobScheduler(config)
    
    # Register job handlers
    scheduler.register_handler('scrape_links', scrape_links_handler)
    scheduler.register_handler('scrape_members', scrape_members_handler)
    
    print("=== Job Scheduler Example ===\n")
    
    # Example 1: Create a link scraping job
    print("1. Creating a link scraping job...")
    link_job = JobConfig(
        job_id='link_scraper_daily',
        job_type='scrape_links',
        schedule_interval=12,  # Every 12 hours
        target_channel='@example_channel',
        parameters={
            'days_back': 1,
            'output_dir': 'data/links'
        },
        enabled=True
    )
    
    await scheduler.create_job(link_job)
    print(f"✓ Created job: {link_job.job_id}\n")
    
    # Example 2: Create a member scraping job
    print("2. Creating a member scraping job...")
    member_job = JobConfig(
        job_id='member_scraper_weekly',
        job_type='scrape_members',
        schedule_interval=168,  # Every week
        target_channel='@example_channel',
        parameters={
            'max_members': 10000,
            'fallback_to_messages': True
        },
        enabled=True
    )
    
    await scheduler.create_job(member_job)
    print(f"✓ Created job: {member_job.job_id}\n")
    
    # Example 3: List all jobs
    print("3. Listing all jobs...")
    jobs = scheduler.list_jobs()
    for job in jobs:
        print(f"  - {job.config.job_id}: {job.config.job_type} "
              f"(every {job.config.schedule_interval}h)")
    print()
    
    # Example 4: Start the scheduler
    print("4. Starting scheduler...")
    await scheduler.start()
    print("✓ Scheduler started\n")
    
    # Example 5: Run a job immediately
    print("5. Running link scraping job immediately...")
    await scheduler.run_job_now('link_scraper_daily')
    
    job = scheduler.get_job('link_scraper_daily')
    print(f"✓ Job status: {job.status}")
    if job.last_run:
        from datetime import datetime
        last_run = datetime.fromtimestamp(job.last_run)
        print(f"  Last run: {last_run.strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    # Example 6: Update a job
    print("6. Updating member scraping job interval...")
    member_job.schedule_interval = 24  # Change to daily
    await scheduler.update_job(member_job)
    print(f"✓ Updated job interval to {member_job.schedule_interval} hours\n")
    
    # Example 7: Display job details
    print("7. Job details:")
    for job in scheduler.list_jobs():
        print(f"\n  Job: {job.config.job_id}")
        print(f"    Type: {job.config.job_type}")
        print(f"    Interval: {job.config.schedule_interval} hours")
        print(f"    Enabled: {job.config.enabled}")
        print(f"    Status: {job.status}")
        if job.config.target_channel:
            print(f"    Target: {job.config.target_channel}")
    print()
    
    # Example 8: Delete a job
    print("8. Deleting member scraping job...")
    await scheduler.delete_job('member_scraper_weekly')
    print("✓ Job deleted\n")
    
    # Example 9: Final job list
    print("9. Final job list:")
    jobs = scheduler.list_jobs()
    print(f"  Total jobs: {len(jobs)}")
    for job in jobs:
        print(f"  - {job.config.job_id}")
    print()
    
    # Stop the scheduler
    print("10. Stopping scheduler...")
    await scheduler.stop()
    print("✓ Scheduler stopped\n")
    
    print("=== Example Complete ===")


async def interactive_example():
    """
    Interactive CLI example
    
    This demonstrates how to use the JobSchedulerCLI for interactive
    job management.
    """
    # Initialize
    config = ConfigManager(config_path='cli/config_example.json')
    await config.load()
    
    scheduler = JobScheduler(config)
    
    # Register handlers
    scheduler.register_handler('scrape_links', scrape_links_handler)
    scheduler.register_handler('scrape_members', scrape_members_handler)
    
    # Start scheduler
    await scheduler.start()
    
    # Create CLI interface
    cli = JobSchedulerCLI(scheduler)
    
    # Show interactive menu
    # Note: This will block until user exits
    cli.show_menu()
    
    # Cleanup
    await scheduler.stop()


if __name__ == '__main__':
    # Run the programmatic example
    asyncio.run(main())
    
    # Uncomment to run the interactive example instead:
    # asyncio.run(interactive_example())
