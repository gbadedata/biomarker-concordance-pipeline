process GATK_BQSR {
    tag "${meta.id}"
    label 'process_medium'
    container 'broadinstitute/gatk:4.5.0.0'

    input:
    tuple val(meta), path(bam), path(bai)
    path fasta
    path fasta_fai
    path fasta_dict
    path dbsnp
    path dbsnp_tbi
    path known_indels
    path known_indels_tbi

    output:
    tuple val(meta), path('*.bqsr.bam'),     emit: bam
    tuple val(meta), path('*.bqsr.bam.bai'), emit: bai
    tuple val(meta), path('*.recal.table'),  emit: recal_table
    path 'versions.yml',                     emit: versions

    script:
    def prefix    = meta.id
    def avail_mem = (task.memory.giga * 0.8).intValue()
    """
    gatk --java-options "-Xmx${avail_mem}g" BaseRecalibrator \\
        --input ${bam} \\
        --reference ${fasta} \\
        --known-sites ${dbsnp} \\
        --known-sites ${known_indels} \\
        --output ${prefix}.recal.table

    gatk --java-options "-Xmx${avail_mem}g" ApplyBQSR \\
        --input ${bam} \\
        --reference ${fasta} \\
        --bqsr-recal-file ${prefix}.recal.table \\
        --output ${prefix}.bqsr.bam \\
        --create-output-bam-index true

    if [ -f "${prefix}.bqsr.bai" ]; then mv ${prefix}.bqsr.bai ${prefix}.bqsr.bam.bai; fi

    cat <<-VERSIONS > versions.yml
    "${task.process}":
        gatk: \$(gatk --version 2>&1 | grep -o '[0-9]\\+\\.[0-9]\\+\\.[0-9]\\+\\.[0-9]\\+' | head -1)
    VERSIONS
    """

    stub:
    def prefix = meta.id
    """
    touch ${prefix}.bqsr.bam ${prefix}.bqsr.bam.bai ${prefix}.recal.table
    cat <<-VERSIONS > versions.yml
    "${task.process}":
        gatk: 4.5.0.0
    VERSIONS
    """
}
