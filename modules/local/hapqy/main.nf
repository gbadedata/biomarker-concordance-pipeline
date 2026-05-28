process HAPQY {
    tag "${meta.id}"
    label 'process_medium'
    // Built locally from Illumina/hap.py v0.3.15 — see README for build instructions
    container 'hap.py:0.3.15'

    input:
    tuple val(meta), path(query_vcf), path(query_tbi)
    path truth_vcf
    path truth_tbi
    path truth_bed
    path fasta
    path fasta_fai

    output:
    tuple val(meta), path('*.summary.csv'),  emit: summary
    tuple val(meta), path('*.extended.csv'), emit: extended
    tuple val(meta), path('*.roc.all.csv'),  emit: roc
    path 'versions.yml',                     emit: versions

    script:
    def prefix = meta.id
    """
    export HGREF=${fasta}

    hap.py \\
        ${truth_vcf} \\
        ${query_vcf} \\
        --reference ${fasta} \\
        --confident-regions ${truth_bed} \\
        --output ${prefix} \\
        --threads ${task.cpus} \\
        --engine xcmp \\
        --type ga4gh \\
        --decompose

    cat <<-VERSIONS > versions.yml
    "${task.process}":
        hapqy: \$(hap.py --version 2>&1 | head -1 | awk '{print \$NF}')
    VERSIONS
    """

    stub:
    def prefix = meta.id
    """
    touch ${prefix}.summary.csv ${prefix}.extended.csv ${prefix}.roc.all.csv
    cat <<-VERSIONS > versions.yml
    "${task.process}":
        hapqy: 0.3.15
    VERSIONS
    """
}
